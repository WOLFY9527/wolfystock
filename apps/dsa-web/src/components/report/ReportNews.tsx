import type React from 'react';
import { useEffect, useState } from 'react';
import type { ParsedApiError } from '../../api/error';
import { getParsedApiError } from '../../api/error';
import { ApiErrorAlert } from '../common/ApiErrorAlert';
import { Card } from '../common/Card';
import { SupportPanel } from '../common/SupportSurface';
import { historyApi } from '../../api/history';
import type { NewsIntelItem, ReportLanguage } from '../../types/analysis';
import { getReportText, normalizeReportLanguage } from '../../utils/reportLanguage';

interface ReportNewsProps {
  recordId?: number;  // 分析历史记录主键 ID
  limit?: number;
  language?: ReportLanguage;
}

/**
 * 资讯区组件 - 产品工作台风格
 */
export const ReportNews: React.FC<ReportNewsProps> = ({ recordId, limit = 8, language = 'zh' }) => {
  if (!recordId) {
    return null;
  }

  return (
    <ReportNewsBody
      key={`${recordId}:${limit}`}
      recordId={recordId}
      limit={limit}
      language={language}
    />
  );
};

interface ReportNewsBodyProps {
  recordId: number;
  limit: number;
  language: ReportLanguage;
}

interface ReportNewsState {
  isLoading: boolean;
  items: NewsIntelItem[];
  error: ParsedApiError | null;
}

const initialReportNewsState: ReportNewsState = {
  isLoading: true,
  items: [],
  error: null,
};

const ReportNewsBody: React.FC<ReportNewsBodyProps> = ({ recordId, limit, language }) => {
  const reportLanguage = normalizeReportLanguage(language);
  const text = getReportText(reportLanguage);
  const loadingCopy = text.loadingNewsBody;
  const [newsState, setNewsState] = useState<ReportNewsState>(initialReportNewsState);
  const { isLoading, items, error } = newsState;

  const fetchNews = () => {
    setNewsState((currentState) => ({ ...currentState, isLoading: true, error: null }));

    void historyApi.getNews(recordId, limit)
      .then((response) => {
        setNewsState({ isLoading: false, items: response.items || [], error: null });
      })
      .catch((err) => {
        setNewsState((currentState) => ({
          ...currentState,
          isLoading: false,
          error: getParsedApiError(err),
        }));
      });
  };

  useEffect(() => {
    let active = true;
    void historyApi.getNews(recordId, limit)
      .then((response) => {
        if (!active) {
          return;
        }
        setNewsState({ isLoading: false, items: response.items || [], error: null });
      })
      .catch((err) => {
        if (!active) {
          return;
        }
        setNewsState({ isLoading: false, items: [], error: getParsedApiError(err) });
      });

    return () => {
      active = false;
    };
  }, [recordId, limit]);

  return (
    <Card variant="bordered" padding="md" className="home-panel-card">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="flex items-baseline gap-2">
          <span className="label-uppercase">{text.newsFeed}</span>
          <h3 className="text-[1.1rem] font-normal tracking-[-0.02em] text-foreground">{text.relatedNews}</h3>
        </div>
        <div className="flex items-center gap-2">
          {isLoading && (
            <div className="home-spinner size-3.5 animate-spin border-2" />
          )}
          <button
            type="button"
            onClick={fetchNews}
            className="home-accent-link text-xs"
          >
            {text.refresh}
          </button>
        </div>
      </div>

      {error && !isLoading && (
        <ApiErrorAlert
          error={error}
          actionLabel={text.retry}
          onAction={fetchNews}
          dismissLabel={text.dismiss}
        />
      )}

      {isLoading && !error && (
        <SupportPanel
          title={text.loadingNews}
          className="report-empty-state"
          bodyClassName="mt-0"
          body={(
            <div className="flex items-center gap-2 text-xs text-secondary-text">
              <span>{loadingCopy}</span>
              <div className="home-spinner size-4 animate-spin border-2" />
            </div>
          )}
        />
      )}

      {!isLoading && !error && items.length === 0 && (
        <SupportPanel
          title={text.relatedNews}
          body={text.noNews}
          className="report-empty-state"
          titleClassName="report-empty-state-title"
          bodyClassName="report-empty-state-body"
        />
      )}

      {!isLoading && !error && items.length > 0 && (
        <div className="space-y-3 text-left">
          {items.map((item, index) => (
            <div
              key={`${item.title}-${index}`}
              className="home-subpanel group p-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0 text-left">
                  <p className="text-[0.98rem] font-normal leading-6 tracking-[-0.01em] text-foreground text-left">
                    {item.title}
                  </p>
                  {item.snippet && (
                    <p className="mt-2 text-sm leading-6 text-secondary-text text-left overflow-hidden [display:-webkit-box] [-webkit-line-clamp:3] [-webkit-box-orient:vertical]">
                      {item.snippet}
                    </p>
                  )}
                </div>
                {item.url && (
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="home-accent-pill-link shrink-0 whitespace-nowrap px-2.5 py-1 text-xs"
                  >
                    {text.openLink}
                    <svg className="size-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M14 3h7m0 0v7m0-7L10 14"
                      />
                    </svg>
                  </a>
                )}
              </div>
            </div>
          ))}

        </div>
      )}
    </Card>
  );
};
