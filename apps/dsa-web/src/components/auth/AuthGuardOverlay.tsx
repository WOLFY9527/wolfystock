import type React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
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
    <div
      className="z-40 flex w-full flex-1 items-center justify-center bg-[#030303]/80 backdrop-blur-sm"
      data-testid="auth-guard-shell"
    >
      <div
        className="w-[360px] max-w-[calc(100%-2rem)] bg-white/[0.02] border border-white/5 rounded-[24px] p-8 flex flex-col items-center text-center shadow-2xl"
        data-testid="auth-guard-card"
      >
        <div className="w-12 h-12 rounded-full bg-white/5 flex items-center justify-center mb-5">
          <svg className="w-5 h-5 text-white/50" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 0 0 2-2v-6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2Zm10-10V7a4 4 0 0 0-8 0v4h8Z" />
          </svg>
        </div>
        <h3 className="text-base font-bold text-white mb-2 tracking-wide">{title}</h3>
        <p className="text-xs text-white/40 mb-8 leading-relaxed">{body}</p>
        <button
          type="button"
          className="w-full py-3 bg-white text-black font-bold text-sm rounded-xl hover:bg-white/90 active:scale-95 transition-all"
          onClick={() => navigate(loginPath)}
        >
          {buttonLabel}
        </button>
      </div>
    </div>
  );
};
