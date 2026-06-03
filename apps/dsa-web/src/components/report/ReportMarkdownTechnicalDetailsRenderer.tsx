import type React from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface ReportMarkdownTechnicalDetailsRendererProps {
  markdown: string;
}

export const ReportMarkdownTechnicalDetailsRenderer: React.FC<ReportMarkdownTechnicalDetailsRendererProps> = ({
  markdown,
}) => (
  <div
    className="home-markdown-prose prose prose-invert max-w-none
      prose-headings:text-foreground prose-headings:font-semibold prose-headings:tracking-tight
      prose-h1:mt-0 prose-h1:mb-4 prose-h1:text-[1.75rem] prose-h1:leading-tight
      prose-h2:mt-8 prose-h2:mb-3 prose-h2:text-[1.35rem] prose-h2:leading-snug
      prose-h3:mt-6 prose-h3:mb-2 prose-h3:text-[1.1rem] prose-h3:leading-snug
      prose-h4:mt-5 prose-h4:mb-2 prose-h4:text-base prose-h4:leading-snug
      prose-p:my-3 prose-p:leading-7 prose-p:last:mb-0
      prose-strong:text-foreground prose-strong:font-semibold
      prose-ul:my-3 prose-ol:my-3 prose-li:my-1 prose-li:leading-7
      prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:before:content-none prose-code:after:content-none
      prose-pre:my-4 prose-pre:border prose-pre:rounded-xl prose-pre:bg-[hsl(var(--elevated)/0.92)] prose-pre:p-4 prose-pre:text-xs prose-pre:leading-6
      prose-table:my-4 prose-table:block prose-table:overflow-x-auto prose-table:no-scrollbar prose-table:rounded-xl prose-table:border prose-table:border-[var(--home-prose-border)]
      prose-th:border prose-th:border-[var(--home-prose-border-strong)] prose-th:px-3 prose-th:py-2 prose-th:uppercase prose-th:tracking-[0.12em]
      prose-td:border prose-td:border-[var(--home-prose-border-strong)] prose-td:px-3 prose-td:py-2 prose-td:align-top
      prose-hr:my-6
      prose-a:no-underline hover:prose-a:underline
      prose-blockquote:my-4 prose-blockquote:border-l prose-blockquote:border-[var(--home-prose-blockquote-border)] prose-blockquote:bg-[var(--home-prose-blockquote-bg)] prose-blockquote:px-4 prose-blockquote:py-3 prose-blockquote:text-secondary-text
      break-words
    "
    data-testid="report-technical-details-renderer"
  >
    <Markdown remarkPlugins={[remarkGfm]}>
      {markdown}
    </Markdown>
  </div>
);
