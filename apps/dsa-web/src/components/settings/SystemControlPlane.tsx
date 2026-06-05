import type React from 'react';
import { Button } from '../common/Button';
import { DensityRail } from '../guidance/DensityRail';
import { GuidedDisclosure } from '../guidance/GuidedDisclosure';
import { InsightStack } from '../guidance/InsightStack';
import { SectionIntro } from '../guidance/SectionIntro';
import {
  describeSettingsSystemHealthStatus,
  type DisplayStatusTone,
} from '../../utils/displayStatus';
import { SettingsAlert } from './SettingsAlert';
import DuckDBQuantPanel from './DuckDBQuantPanel';
import type {
  BentoHeroItem,
  DeveloperDetailGroup,
  SystemHealthStatusCard,
  SystemHealthSummaryCard,
} from './settingsDerivedState';

type AdminActionDialogKey = 'runtime_cache' | 'factory_reset' | null;
type DuckDBConfigState = 'enabled' | 'disabled' | 'unknown';

type TranslateFn = (key: string, vars?: Record<string, string | number | undefined>) => string;

const GHOST_TAG_CLASS = 'inline-flex items-center px-1.5 py-0.5 rounded text-[10px] uppercase tracking-widest font-bold bg-white/5 text-white/40 border border-white/5';
const CONTROL_GHOST_BUTTON_CLASS = 'px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/10 hover:bg-white/10 text-xs transition-colors';
const DISCLOSURE_SUMMARY_CLASS = 'flex min-h-[58px] cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-left outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/40 [&::-webkit-details-marker]:hidden';
const INTENT_PANEL_CLASS = 'min-w-0 rounded-[16px] border border-white/5 bg-black/20 p-3';
const STATUS_ROW_CLASS = 'min-w-0 rounded-xl border border-white/[0.04] bg-white/[0.025] p-3';
const STATUS_CLASS: Record<DisplayStatusTone, string> = {
  success: 'border-emerald-400/20 text-emerald-300 bg-emerald-400/[0.06]',
  warning: 'border-amber-300/20 text-amber-300 bg-amber-300/[0.06]',
  danger: 'border-rose-400/20 text-rose-300 bg-rose-400/[0.06]',
  info: 'border-cyan-300/15 text-cyan-200 bg-cyan-300/[0.05]',
  muted: 'border-white/10 text-white/45 bg-white/[0.03]',
  neutral: 'border-white/10 text-white/45 bg-white/[0.03]',
};
const STATUS_TEXT_CLASS: Record<DisplayStatusTone, string> = {
  success: 'text-emerald-300',
  warning: 'text-amber-300',
  danger: 'text-rose-300',
  info: 'text-cyan-200',
  muted: 'text-white/45',
  neutral: 'text-white/45',
};

type SystemControlPlaneProps = {
  t: TranslateFn;
  overviewStats: BentoHeroItem[];
  summaryCards: SystemHealthSummaryCard[];
  statusCards: SystemHealthStatusCard[];
  developerDetails: DeveloperDetailGroup[];
  isRunningAdminAction: boolean;
  adminActionDialog: AdminActionDialogKey;
  adminActionMessage: string | null;
  adminActionTone: 'success' | 'error';
  duckdbConfigEnabledState: DuckDBConfigState;
  onOpenAdminLogs: () => void;
  onSetAdminActionDialog: (value: Exclude<AdminActionDialogKey, null>) => void;
};

type StatusRowsProps = {
  cards: SystemHealthStatusCard[];
};

const StatusRows: React.FC<StatusRowsProps> = ({ cards }) => (
  <div className="mt-3 grid gap-2">
    {cards.map((card) => {
      const status = describeSettingsSystemHealthStatus(card.status);
      return (
        <article key={card.key} className={STATUS_ROW_CLASS}>
          <div className="flex min-w-0 items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-foreground">{card.label}</p>
              <p className="mt-1 line-clamp-2 text-xs leading-5 text-white/52">{card.reason}</p>
            </div>
            <span className={`shrink-0 rounded-full border px-2 py-1 text-[10px] font-semibold ${STATUS_CLASS[status.tone]}`}>
              {status.label}
            </span>
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-white/35">
            {card.optional ? <span className="rounded-full border border-cyan-300/15 bg-cyan-300/[0.05] px-2 py-1 text-cyan-200">可选</span> : null}
            <span>{card.checkedAt || '最近检查：当前快照'}</span>
          </div>
          {card.nextAction ? <p className="mt-2 text-[11px] leading-5 text-white/45">下一步：{card.nextAction}</p> : null}
        </article>
      );
    })}
  </div>
);

type SystemHealthSummaryProps = {
  summaryCards: SystemHealthSummaryCard[];
};

const SystemHealthSummary: React.FC<SystemHealthSummaryProps> = ({ summaryCards }) => (
  <section
    data-testid="system-health-summary"
    className="rounded-[16px] border border-white/5 bg-white/[0.02] p-4 backdrop-blur-md"
  >
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-cyan-300">当前状态</p>
        <p className="mt-1 text-sm font-semibold text-foreground">系统健康、可用能力、待处理风险和检查快照先合并查看</p>
      </div>
      <span className={GHOST_TAG_CLASS}>当前配置快照</span>
    </div>
    <div className="mt-4 grid grid-cols-2 gap-2 lg:grid-cols-4">
      {summaryCards.map((item) => (
        <div key={item.key} className="min-w-0 rounded-xl border border-white/5 bg-black/20 p-3">
          <p className="truncate text-[10px] font-semibold uppercase tracking-[0.14em] text-white/35">{item.label}</p>
          <p className={`mt-2 truncate text-sm font-semibold ${item.status ? STATUS_TEXT_CLASS[describeSettingsSystemHealthStatus(item.status).tone] : 'text-white'}`}>
            {item.value}
          </p>
          <p className="mt-1 truncate text-[11px] text-white/45">{item.detail}</p>
        </div>
      ))}
    </div>
  </section>
);

type SystemPrioritySettingsProps = {
  t: TranslateFn;
  safetyCards: SystemHealthStatusCard[];
  dataAccessCards: SystemHealthStatusCard[];
  adminEntryCards: SystemHealthStatusCard[];
  onOpenAdminLogs: () => void;
  priorityGroupingSummary: string;
  dataSourceStatusTitle: string;
  dataSourceStatusDesc: string;
};

const SystemPrioritySettings: React.FC<SystemPrioritySettingsProps> = ({
  t,
  safetyCards,
  dataAccessCards,
  adminEntryCards,
  onOpenAdminLogs,
  priorityGroupingSummary,
  dataSourceStatusTitle,
  dataSourceStatusDesc,
}) => (
  <section
    data-testid="system-priority-settings"
    className="rounded-[16px] border border-white/5 bg-white/[0.02] p-4 backdrop-blur-md"
  >
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/45">风险与操作意图</p>
        <p className="mt-1 text-sm font-semibold text-foreground">{priorityGroupingSummary}</p>
      </div>
      <span className={GHOST_TAG_CLASS}>IA 分组</span>
    </div>
    <div data-testid="system-subsystem-cards" className="mt-4 grid grid-cols-1 gap-3 xl:grid-cols-3">
      <section data-testid="system-credential-boundary" className={INTENT_PANEL_CLASS}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-white">安全与凭证</h3>
            <p className="mt-1 text-xs leading-5 text-white/45">只展示凭证就绪状态；不显示密钥、token、Webhook 或未遮蔽原值。</p>
          </div>
          <span className={GHOST_TAG_CLASS}>敏感</span>
        </div>
        <StatusRows cards={safetyCards} />
      </section>

      <section data-testid="system-data-probe-boundary" className={INTENT_PANEL_CLASS}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-white">{dataSourceStatusTitle}</h3>
            <p className="mt-1 text-xs leading-5 text-white/45">{dataSourceStatusDesc}</p>
          </div>
          <span className={GHOST_TAG_CLASS}>探测二级</span>
        </div>
        <StatusRows cards={dataAccessCards} />
      </section>

      <section data-testid="system-admin-entry-boundary" className={INTENT_PANEL_CLASS}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-white">管理入口</h3>
            <p className="mt-1 text-xs leading-5 text-white/45">审计日志和运行边界入口集中呈现，危险动作留在下方隔离区。</p>
          </div>
          <span className={GHOST_TAG_CLASS}>入口</span>
        </div>
        <StatusRows cards={adminEntryCards} />
        <div className="mt-3 flex justify-end">
          <Button
            type="button"
            size="sm"
            variant="settings-secondary"
            className={CONTROL_GHOST_BUTTON_CLASS}
            onClick={onOpenAdminLogs}
          >
            {t('settings.viewAdminLogs')}
          </Button>
        </div>
      </section>
    </div>
  </section>
);

type RiskBoundaryStripProps = {
  cards: SystemHealthStatusCard[];
};

const RiskBoundaryStrip: React.FC<RiskBoundaryStripProps> = ({ cards }) => (
  <section
    data-testid="system-risk-boundary-strip"
    className="rounded-[16px] border border-white/5 bg-white/[0.02] p-4 backdrop-blur-md"
  >
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/45">风险边界</p>
        <h3 className="mt-1 text-sm font-semibold text-white">运行能力与可选模块</h3>
      </div>
      <span className={GHOST_TAG_CLASS}>只读汇总</span>
    </div>
    <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
      {cards.map((card) => {
        const status = describeSettingsSystemHealthStatus(card.status);
        return (
          <article key={card.key} className="rounded-xl border border-white/[0.04] bg-black/20 p-3">
            <div className="flex items-center justify-between gap-3">
              <p className="truncate text-sm font-semibold text-foreground">{card.label}</p>
              <span className={`shrink-0 rounded-full border px-2 py-1 text-[10px] font-semibold ${STATUS_CLASS[status.tone]}`}>
                {status.label}
              </span>
            </div>
            <p className="mt-2 line-clamp-2 text-xs leading-5 text-white/50">{card.reason}</p>
          </article>
        );
      })}
    </div>
  </section>
);

type DeveloperCompatibilityDisclosureProps = {
  compatibilityCards: SystemHealthStatusCard[];
  duckdbConfigEnabledState: DuckDBConfigState;
  compatibilitySummaryTitle: string;
  compatibilitySummaryDesc: string;
  compatibilityStatusEyebrow: string;
};

const DeveloperCompatibilityDisclosure: React.FC<DeveloperCompatibilityDisclosureProps> = ({
  compatibilityCards,
  duckdbConfigEnabledState,
  compatibilitySummaryTitle,
  compatibilitySummaryDesc,
  compatibilityStatusEyebrow,
}) => (
  <details
    data-testid="system-duckdb-disclosure"
    className="group rounded-[16px] border border-white/5 bg-white/[0.02] backdrop-blur-md transition-colors open:border-cyan-200/15 open:bg-white/[0.03]"
  >
    <summary className={DISCLOSURE_SUMMARY_CLASS}>
      <span className="min-w-0">
        <span className="block text-sm font-semibold text-white">{compatibilitySummaryTitle}</span>
        <span className="mt-1 block text-xs leading-5 text-white/48">{compatibilitySummaryDesc}</span>
      </span>
      <span className={GHOST_TAG_CLASS}>深层配置</span>
    </summary>
    <div className="grid gap-4 border-t border-white/[0.04] p-4">
      {compatibilityCards.length ? (
        <section className="rounded-2xl border border-white/5 bg-black/20 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/40">{compatibilityStatusEyebrow}</p>
              <p className="mt-1 text-sm font-semibold text-white">可选依赖和深层引擎只做状态提示</p>
            </div>
            <span className={GHOST_TAG_CLASS}>可选</span>
          </div>
          <StatusRows cards={compatibilityCards} />
        </section>
      ) : null}
      <DuckDBQuantPanel configEnabledState={duckdbConfigEnabledState} />
    </div>
  </details>
);

const SystemControlPlane: React.FC<SystemControlPlaneProps> = ({
  t,
  overviewStats,
  summaryCards,
  statusCards,
  developerDetails,
  isRunningAdminAction,
  adminActionDialog,
  adminActionMessage,
  adminActionTone,
  duckdbConfigEnabledState,
  onOpenAdminLogs,
  onSetAdminActionDialog,
}) => {
  const healthCard = summaryCards.find((item) => item.key === 'health');
  const healthTone = describeSettingsSystemHealthStatus(healthCard?.status || 'unknown').tone;
  const introTone = healthTone === 'success' ? 'ready' : healthTone === 'danger' ? 'risk' : 'watch';
  const isEnglish = t('settings.controlPlaneTitle') === 'Global Control Plane Overview';
  const copy = {
    operationsCenterEyebrow: isEnglish ? 'System Operations Center' : '系统运维中心',
    operationsOverviewTitle: isEnglish ? 'Operations Overview' : '运维总览',
    operationsContextTitle: isEnglish ? 'Runtime Context' : '运行上下文',
    compatibilitySummaryTitle: isEnglish ? 'Compatibility Summary' : '配置兼容摘要',
    dataSourceStatusTitle: isEnglish ? 'Data Source Status' : '数据源状态',
    dataSourceStatusDesc: isEnglish
      ? 'Data paths and remote checks only expose status here; open data-source details when deeper diagnostics are needed.'
      : '数据路径和远端校验只给出状态；需要深层诊断时再进入数据源详情显式触发。',
    compatibilitySummaryDesc: isEnglish
      ? 'DuckDB, config keys, diagnostic summaries, and environment context stay collapsed by default instead of taking first-viewport focus.'
      : 'DuckDB、配置键、诊断摘要和环境上下文默认收起，不作为首屏焦点。',
    compatibilityStatusEyebrow: isEnglish ? 'Compatibility status' : '兼容摘要状态',
    introSummary: isEnglish
      ? `Can the system operate safely right now: ${healthCard?.value || 'Awaiting snapshot'}. Start from the operations overview, then enter a specific configuration group.`
      : `系统当前能否安全运行：${healthCard?.value || '等待快照'}。先看运维总览，再进入具体配置组。`,
    introNextStep: isEnglish
      ? 'Prioritize risk items first. Credentials, data-source status, and admin entry stay in the first viewport; compatibility summaries, remote checks, reloads, and dangerous actions remain secondary.'
      : '优先处理风险项；安全凭证、数据源状态、管理入口在首屏分区呈现，配置兼容摘要、远端校验、重载和危险动作保持二级。',
    activeTitle: isEnglish ? 'You are in the system operations center' : '当前已进入系统运维中心',
    guidedDisclosureSummary: isEnglish
      ? 'Technical detail: config keys, diagnostic summaries, and environment context stay collapsed by default and open only for admin troubleshooting.'
      : '技术细节：配置键、诊断摘要和环境上下文默认收起，仅供管理员排障时展开。',
    guidedDisclosureBeginner: isEnglish
      ? 'Start with system health and the main settings groups during normal operation. This area exists for troubleshooting and compatibility checks, not for deciding whether routine configuration should be saved.'
      : '日常操作先看系统健康和重要设置组；这里主要帮助排障和兼容核对，不用于判断是否保存常规配置。',
    priorityGroupingSummary: isEnglish
      ? 'Grouped by WolfyStock operator intent so config keys and probe controls do not dominate the first viewport.'
      : '按 WolfyStock 运维意图分组，不把配置键或探测按钮铺在首屏',
  };
  const attentionCards = statusCards.filter((card) => (
    card.status === 'attention'
    || card.status === 'not_configured'
    || card.status === 'unavailable'
    || card.status === 'unknown'
  ));
  const insightCards = attentionCards.length ? attentionCards.slice(0, 4) : statusCards.slice(0, 3);
  const railItems = overviewStats.slice(0, 4).map((item, index) => ({
    id: `overview-${index}`,
    label: item.label,
    value: item.value,
    helper: typeof item.detail === 'string' ? item.detail : undefined,
    tone: item.tone === 'bullish' ? 'positive' as const : item.tone === 'bearish' ? 'negative' as const : 'neutral' as const,
  }));
  const statusByKey = new Map(statusCards.map((card) => [card.key, card]));
  const cardsByKey = (keys: string[]) => keys
    .map((key) => statusByKey.get(key))
    .filter((card): card is SystemHealthStatusCard => Boolean(card));
  const safetyCards = cardsByKey(['ai', 'notification']);
  const dataAccessCards = cardsByKey(['data_sources', 'market_overview', 'scanner']);
  const riskBoundaryCards = cardsByKey(['backtest', 'portfolio']);
  const compatibilityCards = statusCards.filter((card) => (
    card.key === 'duckdb'
    || card.optional
  ));
  const adminEntryCards = cardsByKey(['logs']);

  return (
    <section className="space-y-5" aria-labelledby="system-control-plane-heading">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-cyan-100/55">{copy.operationsCenterEyebrow}</p>
          <h2 id="system-control-plane-heading" className="mt-1 text-xl font-semibold tracking-normal text-white">
            {copy.operationsOverviewTitle}
          </h2>
        </div>
        <span className={GHOST_TAG_CLASS}>{t('settings.adminSurfaceGlobalScope')}</span>
      </div>

      <div
        data-testid="system-operator-dashboard"
        className="grid gap-5 xl:grid-cols-[minmax(0,1.38fr)_minmax(20rem,0.62fr)]"
      >
        <div className="min-w-0 space-y-5">
          <SectionIntro
            purpose="当前状态"
            summary={copy.introSummary}
            nextStep={copy.introNextStep}
            status={{ label: String(healthCard?.value || '等待配置快照'), tone: introTone }}
          />

          <SystemHealthSummary summaryCards={summaryCards} />

          <SystemPrioritySettings
            t={t}
            safetyCards={safetyCards}
            dataAccessCards={dataAccessCards}
            adminEntryCards={adminEntryCards}
            onOpenAdminLogs={onOpenAdminLogs}
            priorityGroupingSummary={copy.priorityGroupingSummary}
            dataSourceStatusTitle={copy.dataSourceStatusTitle}
            dataSourceStatusDesc={copy.dataSourceStatusDesc}
          />
        </div>

        <div className="min-w-0 space-y-5">
          <InsightStack
            title="优先处理"
            insights={insightCards.map((card) => ({
              id: card.key,
              severity: card.status === 'unavailable' ? 'critical' : card.status === 'available' ? 'success' : 'warning',
              title: card.label,
              explanation: card.reason,
              detail: card.nextAction ? `下一步：${card.nextAction}` : '无需进入原始配置即可判断当前状态。',
            }))}
          />
          <div data-testid="settings-bento-hero">
            <DensityRail
              title={copy.operationsContextTitle}
              items={railItems}
              className="md:max-w-none"
            />
            {overviewStats.map((item) => (
              item.valueTestId ? (
                <span key={item.valueTestId} className="sr-only" data-testid={item.valueTestId}>
                  {item.value}
                </span>
              ) : null
            ))}
          </div>
          <div className="rounded-[16px] border border-emerald-300/10 bg-emerald-400/[0.04] p-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-emerald-200/80">
              {t('settings.adminSurfaceActiveLabel')}
            </p>
            <p className="mt-2 text-sm font-semibold text-foreground">{copy.activeTitle}</p>
            <p className="mt-2 text-xs leading-5 text-white/48">常规设置通过左侧分组进入；缓存、重载、危险动作不与常规保存按钮混排。</p>
          </div>
        </div>
      </div>

      <RiskBoundaryStrip cards={riskBoundaryCards} />

      <div data-testid="system-secondary-zones" className="grid gap-4 xl:grid-cols-2">
        <details
          data-testid="system-danger-zone"
          className="group rounded-[16px] border border-amber-300/14 bg-amber-300/[0.035] backdrop-blur-md transition-colors open:border-amber-200/25 open:bg-amber-300/[0.055]"
        >
          <summary className={DISCLOSURE_SUMMARY_CLASS}>
            <span className="min-w-0">
              <span className="block text-sm font-semibold text-amber-100">缓存 / 重载 / 危险动作</span>
              <span className="mt-1 block text-xs font-semibold leading-5 text-white/60">展开缓存维护与初始化动作</span>
              <span className="mt-1 block text-xs leading-5 text-white/52">缓存清理、重载提示和系统初始化保持隔离；确认后才执行。</span>
            </span>
            <span className={GHOST_TAG_CLASS}>二级动作区</span>
          </summary>
          <div className="border-t border-white/[0.04] p-4">
            <div className="rounded-2xl border border-amber-300/16 bg-black/25 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[hsl(var(--accent-warning-hsl))]">
                    {t('settings.adminActionsTitle')}
                  </p>
                  <p className="mt-1 text-sm font-semibold text-foreground">{t('settings.adminActionsDesc')}</p>
                  <p className="mt-2 text-xs leading-5 text-white/46">这里不新增后台动作；仍使用现有确认对话、权限和运行时 API。</p>
                </div>
              </div>
              <div className="mt-4 divide-y divide-white/5 rounded-2xl border border-white/5 bg-white/[0.025]">
                <div className="p-3">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-foreground">{t('settings.adminMaintenanceTitle')}</p>
                      <p className="mt-1 text-xs leading-5 text-white/42">清理缓存前会先进入确认对话。</p>
                    </div>
                    <Button
                      type="button"
                      size="sm"
                      variant="settings-secondary"
                      className={CONTROL_GHOST_BUTTON_CLASS}
                      onClick={() => onSetAdminActionDialog('runtime_cache')}
                      disabled={isRunningAdminAction}
                    >
                      {isRunningAdminAction && adminActionDialog === 'runtime_cache'
                        ? t('settings.saving')
                        : t('settings.adminActionResetRuntimeCaches')}
                    </Button>
                  </div>
                </div>
                <div className="p-3">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-foreground">{t('settings.adminFactoryResetTitle')}</p>
                      <p className="mt-1 text-xs leading-5 text-white/42">高风险重置动作保持在隔离区域内。</p>
                    </div>
                    <Button
                      type="button"
                      size="sm"
                      variant="danger-subtle"
                      data-system-settings-reset-action="factory_reset"
                      onClick={() => onSetAdminActionDialog('factory_reset')}
                      disabled={isRunningAdminAction}
                    >
                      {isRunningAdminAction && adminActionDialog === 'factory_reset'
                        ? t('settings.saving')
                        : t('settings.adminActionFactoryReset')}
                    </Button>
                  </div>
                </div>
              </div>
              {adminActionMessage ? (
                <div className="mt-3">
                  <span className="sr-only">
                    {(adminActionTone === 'success' ? t('settings.success') : t('settings.adminActionErrorTitle'))}:{adminActionMessage}
                  </span>
                  <SettingsAlert
                    title={adminActionTone === 'success' ? t('settings.success') : t('settings.adminActionErrorTitle')}
                    message={adminActionMessage}
                    variant={adminActionTone === 'success' ? 'success' : 'error'}
                  />
                </div>
              ) : null}
            </div>
          </div>
        </details>

        <DeveloperCompatibilityDisclosure
          compatibilityCards={compatibilityCards}
          duckdbConfigEnabledState={duckdbConfigEnabledState}
          compatibilitySummaryTitle={copy.compatibilitySummaryTitle}
          compatibilitySummaryDesc={copy.compatibilitySummaryDesc}
          compatibilityStatusEyebrow={copy.compatibilityStatusEyebrow}
        />

        <GuidedDisclosure
          title={copy.compatibilitySummaryTitle}
          summary={copy.guidedDisclosureSummary}
          beginner={<p>{copy.guidedDisclosureBeginner}</p>}
          professional={(
            <div className="grid gap-3">
              {developerDetails.map((detail) => (
                <div key={detail.key} className="min-w-0 rounded-xl border border-white/5 bg-black/20 p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/35">{detail.label}</p>
                  <p className="mt-2 text-xs leading-5 text-white/55">{detail.detail}</p>
                </div>
              ))}
            </div>
          )}
        />
      </div>
    </section>
  );
};

export default SystemControlPlane;
