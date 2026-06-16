import { Link, useLocation } from 'react-router-dom';
import {
  ConsoleBoard,
  ConsoleContextRail,
  MetricStrip,
  ResearchConsoleShell,
  WolfyCommandBar,
} from '../components/linear/LinearPrimitives';
import { ConsumerWorkspacePageShell, ConsumerWorkspaceScope } from '../components/layout/ConsumerWorkspaceShell';
import { TerminalChip, TerminalEmptyState } from '../components/terminal/TerminalPrimitives';
import { useI18n } from '../contexts/UiLanguageContext';
import { buildLocalizedPath, parseLocaleFromPathname } from '../utils/localeRouting';
import { RoughBulletList, RoughSectionCard, RoughSurfaceIntro } from './roughShellShared';

export default function ScenarioLabPage() {
  const { language } = useI18n();
  const locale = language === 'en' ? 'en' : 'zh';
  const location = useLocation();
  const routeLocale = parseLocaleFromPathname(location.pathname);
  const localize = (path: string) => (routeLocale ? buildLocalizedPath(path, routeLocale) : path);

  return (
    <ConsumerWorkspaceScope className="flex min-h-0 flex-1">
      <ConsumerWorkspacePageShell className="flex min-h-0 flex-1 flex-col gap-4 md:gap-6">
        <ResearchConsoleShell
          className="flex-1"
          command={(
            <WolfyCommandBar
              leading={<span className="text-xs text-[color:var(--wolfy-text-muted)]">{locale === 'en' ? 'Scenario Lab / Placeholder' : '情景实验室 / 占位入口'}</span>}
              trailing={(
                <div className="flex flex-wrap items-center gap-2">
                  <Link
                    to={localize('/market/decision-cockpit')}
                    className="rounded-md border border-[color:var(--wolfy-border-subtle)] px-3 py-1.5 text-xs text-[color:var(--wolfy-text-secondary)] transition-colors hover:text-[color:var(--wolfy-text-primary)]"
                  >
                    {locale === 'en' ? 'Decision cockpit' : '决策驾驶舱'}
                  </Link>
                  <Link
                    to={localize('/options-lab')}
                    className="rounded-md border border-[color:var(--wolfy-border-subtle)] px-3 py-1.5 text-xs text-[color:var(--wolfy-text-secondary)] transition-colors hover:text-[color:var(--wolfy-text-primary)]"
                  >
                    {locale === 'en' ? 'Options/Gamma' : '期权/Gamma'}
                  </Link>
                </div>
              )}
            >
              <div className="text-xs text-[color:var(--wolfy-text-secondary)]">
                {locale === 'en'
                  ? 'Reserved for read-only scenario comparison; no backend contract is called from this placeholder.'
                  : '预留给只读情景对照；当前占位页不调用后端契约。'}
              </div>
            </WolfyCommandBar>
          )}
          rail={(
            <ConsoleContextRail className="flex flex-col gap-3 p-3">
              <RoughSectionCard eyebrow={locale === 'en' ? 'Availability' : '可用性'} title={locale === 'en' ? 'Endpoint not wired here' : '当前未接入接口'}>
                <p className="text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
                  {locale === 'en'
                    ? 'This frontend entry is intentionally static in this branch. It avoids guessing a scenario API contract.'
                    : '本分支的前端入口保持静态，避免臆测情景 API 契约。'}
                </p>
              </RoughSectionCard>
              <RoughSectionCard eyebrow={locale === 'en' ? 'Boundary' : '边界'} title={locale === 'en' ? 'No external action' : '不触发外部动作'}>
                <RoughBulletList
                  items={[
                    locale === 'en' ? 'No external execution or account-connection UI.' : '不提供外部执行或账户连接 UI。',
                    locale === 'en' ? 'No provider/runtime/cache payloads are shown.' : '不展示 provider/runtime/cache 载荷。',
                    locale === 'en' ? 'No portfolio record is read or changed by this placeholder.' : '该占位页不读取或修改组合记录。',
                  ]}
                  emptyText=""
                />
              </RoughSectionCard>
            </ConsoleContextRail>
          )}
        >
          <ConsoleBoard className="min-h-0" data-testid="scenario-lab-page">
            <RoughSurfaceIntro
              eyebrow={locale === 'en' ? 'Scenario Lab' : '情景实验室'}
              title={locale === 'en' ? 'Read-only scenario workbench placeholder' : '只读情景工作台占位入口'}
              description={locale === 'en'
                ? 'Scenario Lab is part of the new research IA, but this pass only exposes the entry and boundary states until a frontend-safe API contract is available.'
                : 'Scenario Lab 属于新版研究 IA；本轮只建立入口与边界状态，等待前端安全 API 契约可用后再接入。'}
            />
            <MetricStrip
              items={[
                { key: 'state', label: locale === 'en' ? 'Current state' : '当前状态', value: locale === 'en' ? 'Placeholder' : '占位入口' },
                { key: 'grade', label: locale === 'en' ? 'Decision grade' : '判断等级', value: 'decisionGrade=false' },
                { key: 'mode', label: locale === 'en' ? 'Mode' : '模式', value: locale === 'en' ? 'Observation only' : '仅观察' },
              ]}
            />
            <div className="grid gap-3 p-3 md:grid-cols-2">
              <RoughSectionCard eyebrow={locale === 'en' ? 'Workflow slot' : '工作流位置'} title={locale === 'en' ? 'Where this belongs' : '它在 IA 中的位置'}>
                <RoughBulletList
                  items={[
                    locale === 'en' ? 'Decision Cockpit frames the market regime first.' : '决策驾驶舱先建立市场状态。',
                    locale === 'en' ? 'Research Radar and Stock Structure provide evidence inputs.' : '研究雷达与个股结构提供证据输入。',
                    locale === 'en' ? 'Options/Gamma stays observation-only until data quality supports review.' : '期权/Gamma 在数据质量不足时保持仅观察。'
                  ]}
                  emptyText=""
                />
              </RoughSectionCard>
              <RoughSectionCard eyebrow={locale === 'en' ? 'Empty state' : '空状态'} title={locale === 'en' ? 'Waiting for safe contract' : '等待安全契约'}>
                <TerminalEmptyState title={locale === 'en' ? 'Scenario engine not connected' : '情景引擎未接入'}>
                  {locale === 'en'
                    ? 'Use existing market, structure, and options observation pages for this IA pass.'
                    : '本轮先使用既有市场、结构与期权观察页完成研究链路。'}
                </TerminalEmptyState>
                <div className="mt-3 flex flex-wrap gap-2">
                  <TerminalChip variant="info">observationOnly=true</TerminalChip>
                  <TerminalChip variant="info">decisionGrade=false</TerminalChip>
                </div>
              </RoughSectionCard>
            </div>
          </ConsoleBoard>
        </ResearchConsoleShell>
      </ConsumerWorkspacePageShell>
    </ConsumerWorkspaceScope>
  );
}
