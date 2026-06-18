import type React from 'react';
import type { ParsedApiError } from '../../api/error';
import { useI18n } from '../../contexts/UiLanguageContext';
import { getConsumerSafeApiErrorCopy } from '../../utils/consumerErrorCopy';
import { SupportBanner } from './SupportSurface';

interface ApiErrorAlertProps {
  error: ParsedApiError;
  className?: string;
  actionLabel?: string;
  onAction?: () => void;
  dismissLabel?: string;
  onDismiss?: () => void;
  allowDetails?: boolean;
}

function getErrorGuidance(
  error: ParsedApiError,
  t: (key: string, vars?: Record<string, string | number | undefined>) => string,
): string[] {
  const errorText = `${error.title} ${error.message} ${error.rawMessage}`.toLowerCase();
  const isSslFailure = /certificate verify failed|certificat.*failed|ssl certificate verification failed|ssl 证书|证书.*验证失败|证书校验失败/i.test(errorText);

  if (isSslFailure) {
    return [
      t('common.apiError.guidance.ssl1'),
      t('common.apiError.guidance.ssl2'),
      t('common.apiError.guidance.ssl3'),
    ];
  }

  if (error.category === 'local_connection_failed') {
    return [
      t('common.apiError.guidance.localConnection1'),
      t('common.apiError.guidance.localConnection2'),
      t('common.apiError.guidance.localConnection3'),
    ];
  }

  if (error.category === 'upstream_timeout' || error.category === 'upstream_network' || error.category === 'upstream_unavailable') {
    return [
      t('common.apiError.guidance.upstream1'),
      t('common.apiError.guidance.upstream2'),
    ];
  }

  if (error.category === 'analysis_conflict') {
    return [
      t('common.apiError.guidance.analysisConflict'),
    ];
  }

  if (error.category === 'auth_required') {
    return [
      t('common.apiError.guidance.authRequired1'),
      t('common.apiError.guidance.authRequired2'),
    ];
  }

  if (error.category === 'admin_unlock_required') {
    return [
      t('common.apiError.guidance.adminUnlock1'),
      t('common.apiError.guidance.adminUnlock2'),
    ];
  }

  if (error.category === 'access_denied') {
    return [
      t('common.apiError.guidance.accessDenied1'),
      t('common.apiError.guidance.accessDenied2'),
    ];
  }

  return [];
}

export const ApiErrorAlert: React.FC<ApiErrorAlertProps> = ({
  error,
  className = '',
  actionLabel,
  onAction,
  dismissLabel,
  onDismiss,
  allowDetails = false,
}) => {
  const { language, t } = useI18n();
  const safeCopy = getConsumerSafeApiErrorCopy(error, {
    language: language === 'en' ? 'en' : 'zh',
    fallbackTitle: language === 'en' ? 'This request is temporarily unavailable.' : '当前请求暂不可用。',
    fallbackMessage: language === 'en' ? 'Please try again shortly.' : '请稍后重试。',
  });
  const guidance = getErrorGuidance(error, t);
  const dismissText = dismissLabel || t('common.apiError.close');
  const shouldRenderDetails = allowDetails && safeCopy.rawMessage.trim().length > 0;

  return (
    <SupportBanner
      tone="danger"
      title={(
        <span className="flex items-start justify-between gap-3">
          <span>{safeCopy.title}</span>
          {onDismiss ? (
            <button
              type="button"
              className="shrink-0 rounded-[var(--theme-button-radius)] border border-[var(--state-danger-border)] bg-[var(--state-danger-bg)] px-2.5 py-1 text-[11px] uppercase tracking-[0.14em] text-[var(--state-danger-text)] transition hover:bg-[var(--state-danger-bg-strong)]"
              onClick={onDismiss}
            >
              {dismissText}
            </button>
          ) : null}
        </span>
      )}
      body={safeCopy.message}
      titleClassName="text-danger"
      bodyClassName="text-danger opacity-90"
      className={className}
      role="alert"
    >
      {shouldRenderDetails ? (
        <details className="theme-panel-subtle mt-3 rounded-[var(--cohere-radius-medium)] p-3">
          <summary className="label-uppercase cursor-pointer text-danger opacity-90">{t('common.apiError.details')}</summary>
          <pre className="mt-2 whitespace-pre-wrap break-words text-[11px] leading-5 text-danger opacity-85">
            {safeCopy.rawMessage}
          </pre>
        </details>
      ) : safeCopy.hasHiddenDetails ? (
        <p className="mt-3 text-xs leading-5 text-secondary-text">
          {t('common.apiError.hiddenDetails')}
        </p>
      ) : null}
      {guidance.length > 0 ? (
        <ul className="theme-panel-subtle mt-3 space-y-1.5 rounded-[var(--cohere-radius-medium)] p-3 text-[11px] leading-5 text-secondary-text">
          {guidance.map((entry) => (
            <li key={entry}>• {entry}</li>
          ))}
        </ul>
      ) : null}
      {actionLabel && onAction ? (
        <button type="button" className="mt-3 btn-secondary !px-3 !py-1.5 !text-xs" onClick={onAction}>
          {actionLabel}
        </button>
      ) : null}
    </SupportBanner>
  );
};
