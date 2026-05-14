import type React from 'react';
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { TerminalButton, TerminalPageShell, TerminalPanel } from '../components/terminal';
import { useI18n } from '../contexts/UiLanguageContext';
import { buildLocalizedPath } from '../utils/localeRouting';

const NotFoundPage: React.FC = () => {
  const { language, t } = useI18n();
  const navigate = useNavigate();
  const homePath = buildLocalizedPath('/', language);

  useEffect(() => {
    document.title = t('notFound.documentTitle');
  }, [t]);

  return (
    <TerminalPageShell className="flex min-h-0 flex-1 justify-center overflow-x-hidden py-8 md:py-10">
      <TerminalPanel as="section" className="mx-auto flex w-full max-w-2xl flex-col items-center self-center px-6 py-10 text-center sm:px-10">
        <p className="label-uppercase text-secondary-text">{t('notFound.eyebrow')}</p>
        <p className="mt-4 text-7xl font-normal tracking-[0.18em] text-foreground sm:text-8xl">404</p>
        <h1 className="mt-5 text-2xl font-normal tracking-[0.08em] text-foreground">{t('notFound.title')}</h1>
        <p className="mx-auto mt-3 max-w-xl text-sm leading-7 text-secondary-text">{t('notFound.body')}</p>
        <div className="mt-8 flex justify-center">
          <TerminalButton type="button" variant="primary" onClick={() => navigate(homePath)}>
            {t('notFound.cta')}
          </TerminalButton>
        </div>
      </TerminalPanel>
    </TerminalPageShell>
  );
};

export default NotFoundPage;
