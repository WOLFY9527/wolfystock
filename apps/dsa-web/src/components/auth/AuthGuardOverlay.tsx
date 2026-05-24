import type React from 'react';
import { useId } from 'react';
import { Lock } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';
import { TerminalButton } from '../terminal';
import { useI18n } from '../../contexts/UiLanguageContext';
import { buildLocalizedPath, parseLocaleFromPathname } from '../../utils/localeRouting';

type AuthGuardOverlayProps = {
  moduleName: string;
  children?: React.ReactNode;
};

export const AuthGuardOverlay: React.FC<AuthGuardOverlayProps> = ({ moduleName, children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { language } = useI18n();
  const titleId = useId();
  const bodyId = useId();
  const routeLocale = parseLocaleFromPathname(location.pathname);
  const loginPath = routeLocale ? buildLocalizedPath('/login', routeLocale) : '/login';
  const title = language === 'en' ? `Sign in to unlock ${moduleName}` : `登录解锁 ${moduleName}`;
  const body = language === 'en'
    ? 'Guest mode only supports the home preview. Personal workspaces, historical review, and advanced metrics require a real account.'
    : '游客模式仅支持首页基础查询。保存个人工作区、深度历史回溯及进阶指标测算，均需绑定正式账户。';
  const buttonLabel = language === 'en' ? 'Sign in / Create account' : '登录 / 创建账户';

  return (
    <section
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      aria-describedby={bodyId}
      data-testid="auth-guard-overlay"
      className="fixed inset-0 z-[80] grid place-items-center overflow-hidden px-4 py-6 sm:px-6"
    >
      {children ? (
        <div
          data-testid="auth-guard-backdrop-content"
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 select-none overflow-hidden blur-[2px] saturate-50"
        >
          {children}
        </div>
      ) : (
        <div
          data-testid="auth-guard-ambient-backdrop"
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 overflow-hidden opacity-80"
        >
          <div className="absolute inset-x-4 top-14 mx-auto grid max-w-6xl gap-4 sm:top-20">
            <div className="h-14 rounded-[14px] border border-white/8 bg-white/[0.035]" />
            <div className="grid gap-4 md:grid-cols-[minmax(0,1.7fr)_minmax(18rem,0.8fr)]">
              <div className="min-h-[26rem] rounded-[14px] border border-white/8 bg-white/[0.03] p-4">
                <div className="mb-5 h-8 w-48 rounded-full bg-white/[0.06]" />
                <div className="grid gap-3">
                  <div className="h-12 rounded-[10px] bg-white/[0.05]" />
                  <div className="h-12 rounded-[10px] bg-white/[0.035]" />
                  <div className="h-12 rounded-[10px] bg-white/[0.045]" />
                  <div className="h-12 rounded-[10px] bg-white/[0.03]" />
                </div>
              </div>
              <div className="hidden min-h-[26rem] rounded-[14px] border border-white/8 bg-white/[0.026] p-4 md:block">
                <div className="mb-4 h-7 w-32 rounded-full bg-white/[0.06]" />
                <div className="space-y-3">
                  <div className="h-16 rounded-[10px] bg-white/[0.04]" />
                  <div className="h-16 rounded-[10px] bg-white/[0.032]" />
                  <div className="h-16 rounded-[10px] bg-white/[0.04]" />
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      <div
        data-testid="auth-guard-scrim"
        className="absolute inset-0 bg-[color:rgba(7,10,18,0.56)] backdrop-blur-md"
        aria-hidden="true"
      />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_18%,rgba(128,136,255,0.13),transparent_34%),linear-gradient(180deg,rgba(255,255,255,0.04),transparent_42%)]" aria-hidden="true" />

      <section
        className="relative z-10 flex w-[min(92vw,28rem)] flex-col items-center overflow-hidden rounded-[14px] border border-white/12 bg-[color:rgba(18,23,35,0.74)] px-5 py-6 text-center shadow-[0_24px_80px_rgba(3,7,18,0.38)] backdrop-blur-2xl sm:px-6 sm:py-7"
        data-testid="auth-guard-card"
      >
        <div className="mx-auto mb-5 flex h-11 w-11 items-center justify-center rounded-full border border-white/12 bg-white/[0.07] text-[color:var(--wolfy-text-muted)] shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]">
          <Lock className="h-4 w-4" aria-hidden="true" />
        </div>
        <h2 id={titleId} className="text-base font-semibold text-[color:var(--wolfy-text-primary)]">{title}</h2>
        <p id={bodyId} className="mx-auto mt-3 max-w-[22rem] text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{body}</p>
        <TerminalButton
          variant="primary"
          className="mt-7 h-11 w-full rounded-[10px] text-sm"
          onClick={() => navigate(loginPath)}
        >
          {buttonLabel}
        </TerminalButton>
      </section>
    </section>
  );
};
