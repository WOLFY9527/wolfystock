import type React from 'react';
import { Lock } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';
import { WideWorkspacePageShell } from '../layout/WideWorkspaceShell';
import { WolfyShellSurface } from '../linear';
import { TerminalButton } from '../terminal';
import { useI18n } from '../../contexts/UiLanguageContext';
import { buildLocalizedPath, parseLocaleFromPathname } from '../../utils/localeRouting';

type AuthGuardOverlayProps = {
  moduleName: string;
};

export const AuthGuardOverlay: React.FC<AuthGuardOverlayProps> = ({ moduleName }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { language } = useI18n();
  const routeLocale = parseLocaleFromPathname(location.pathname);
  const loginPath = routeLocale ? buildLocalizedPath('/login', routeLocale) : '/login';
  const title = language === 'en' ? `Sign in to unlock ${moduleName}` : `登录解锁 ${moduleName}`;
  const body = language === 'en'
    ? 'Guest mode only supports the home preview. Personal workspaces, historical review, and advanced metrics require a real account.'
    : '游客模式仅支持首页基础查询。保存个人工作区、深度历史回溯及进阶指标测算，均需绑定正式账户。';
  const buttonLabel = language === 'en' ? 'Sign in / Create account' : '登录 / 创建账户';

  return (
    <WideWorkspacePageShell
      data-layout-zone="PrimaryWorkRegion"
      data-testid="auth-guard-shell"
      className="flex-1 items-center justify-center py-10"
    >
      <WolfyShellSurface
        as="section"
        variant="console"
        padding="lg"
        className="flex w-full max-w-[28rem] flex-col items-center text-center"
        data-testid="auth-guard-card"
      >
        <div className="mx-auto mb-5 flex h-11 w-11 items-center justify-center rounded-full border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] text-[color:var(--wolfy-text-muted)]">
          <Lock className="h-4 w-4" aria-hidden="true" />
        </div>
        <h3 className="text-base font-semibold text-[color:var(--wolfy-text-primary)]">{title}</h3>
        <p className="mx-auto mt-3 max-w-[22rem] text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{body}</p>
        <TerminalButton
          variant="primary"
          className="mt-7 h-11 w-full text-sm"
          onClick={() => navigate(loginPath)}
        >
          {buttonLabel}
        </TerminalButton>
      </WolfyShellSurface>
    </WideWorkspacePageShell>
  );
};
