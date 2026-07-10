import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { TerminalButton, TerminalPageShell, TerminalPanel } from '../terminal/TerminalPrimitives';
import { useI18n } from '../../contexts/UiLanguageContext';
import { buildLocalizedPath } from '../../utils/localeRouting';

type AppErrorBoundaryState = {
  hasError: boolean;
};

type AppErrorBoundaryInnerProps = {
  children: React.ReactNode;
  eyebrow: string;
  title: string;
  body: string;
  retryLabel: string;
  homeLabel: string;
  onHome: () => void;
};

class AppErrorBoundaryInner extends React.Component<AppErrorBoundaryInnerProps, AppErrorBoundaryState> {
  state: AppErrorBoundaryState = {
    hasError: false,
  };

  private fallbackRef = React.createRef<HTMLElement>();

  static getDerivedStateFromError(): AppErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch() {
    this.fallbackRef.current?.focus({ preventScroll: true });
  }

  componentDidUpdate(_prevProps: AppErrorBoundaryInnerProps, prevState: AppErrorBoundaryState) {
    if (!prevState.hasError && this.state.hasError) {
      this.fallbackRef.current?.focus({ preventScroll: true });
    }
  }

  private handleRetry = () => {
    this.setState({ hasError: false }, () => {
      if (!this.state.hasError) {
        document.getElementById('main-content')?.focus({ preventScroll: true });
      }
    });
  };

  render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    return (
      <TerminalPageShell className="flex min-h-screen flex-1 justify-center overflow-x-hidden px-4 py-8 md:py-10">
        <section
          ref={this.fallbackRef}
          role="alert"
          tabIndex={-1}
          data-testid="app-error-boundary"
          className="mx-auto w-full max-w-2xl outline-none"
        >
          <TerminalPanel className="flex w-full flex-col px-6 py-8 sm:px-10">
            <p className="label-uppercase text-secondary-text">{this.props.eyebrow}</p>
            <h1 className="mt-4 text-2xl font-normal tracking-[0.04em] text-foreground">{this.props.title}</h1>
            <p className="mt-3 max-w-xl text-sm leading-7 text-secondary-text">{this.props.body}</p>
            <div className="mt-8 flex flex-wrap gap-3">
              <TerminalButton type="button" variant="primary" onClick={this.handleRetry}>
                {this.props.retryLabel}
              </TerminalButton>
              <TerminalButton type="button" variant="secondary" onClick={this.props.onHome}>
                {this.props.homeLabel}
              </TerminalButton>
            </div>
          </TerminalPanel>
        </section>
      </TerminalPageShell>
    );
  }
}

export const AppErrorBoundary: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const { language, t } = useI18n();
  const homePath = buildLocalizedPath('/', language);
  const resetKey = `${language}:${location.pathname}${location.search}${location.hash}`;

  return (
    <AppErrorBoundaryInner
      key={resetKey}
      eyebrow={t('app.workspaceEyebrow')}
      title={t('app.errorBoundaryTitle')}
      body={t('app.errorBoundaryBody')}
      retryLabel={t('app.retry')}
      homeLabel={t('notFound.cta')}
      onHome={() => navigate(homePath)}
    >
      {children}
    </AppErrorBoundaryInner>
  );
};
