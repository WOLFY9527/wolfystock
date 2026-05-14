import React from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

type AssistantMarkdownContentProps = {
  content: string;
  className: string;
};

const assistantMarkdownComponents = {
  h1: ({ children }: React.PropsWithChildren) => <h1 className="mb-3 text-lg font-bold text-white">{children}</h1>,
  h2: ({ children }: React.PropsWithChildren) => <h2 className="mb-3 mt-4 text-base font-semibold text-white">{children}</h2>,
  h3: ({ children }: React.PropsWithChildren) => <h3 className="mb-2 mt-4 text-base font-semibold text-white">{children}</h3>,
  p: ({ children }: React.PropsWithChildren) => <p className="mb-2 leading-[1.6] last:mb-0">{children}</p>,
  ul: ({ children }: React.PropsWithChildren) => <ul className="my-2 list-disc space-y-1 pl-5 last:mb-0">{children}</ul>,
  ol: ({ children }: React.PropsWithChildren) => <ol className="my-2 list-decimal space-y-1 pl-5 last:mb-0">{children}</ol>,
  li: ({ children }: React.PropsWithChildren) => <li className="mb-1 break-words leading-[1.6]">{children}</li>,
  strong: ({ children }: React.PropsWithChildren) => <strong className="font-semibold text-white">{children}</strong>,
  a: ({ children, href }: React.PropsWithChildren<{ href?: string }>) => (
    <a className="text-[hsl(var(--accent-primary-hsl))] underline-offset-2 hover:underline" href={href} target="_blank" rel="noreferrer">
      {children}
    </a>
  ),
  blockquote: ({ children }: React.PropsWithChildren) => (
    <blockquote className="my-3 text-white/72 first:mt-0 last:mb-0">{children}</blockquote>
  ),
  code: ({ children, className }: React.PropsWithChildren<{ className?: string }>) => {
    if (className) {
      return <code className={className}>{children}</code>;
    }
    return (
      <code className="rounded bg-white/[0.08] px-1.5 py-0.5 text-xs text-[hsl(var(--accent-primary-hsl))] break-all">
        {children}
      </code>
    );
  },
  pre: ({ children }: React.PropsWithChildren) => (
    <pre className="mb-3 overflow-x-auto no-scrollbar rounded-xl border border-white/8 bg-black/30 p-3 text-[13px] leading-6 text-white/88 last:mb-0">
      {children}
    </pre>
  ),
  table: ({ children }: React.PropsWithChildren) => (
    <div className="mb-4 overflow-x-auto no-scrollbar last:mb-0">
      <table className="w-full min-w-max border-collapse text-sm">{children}</table>
    </div>
  ),
  th: ({ children }: React.PropsWithChildren) => <th className="border border-white/10 bg-white/[0.05] px-3 py-1.5 text-left font-medium text-white">{children}</th>,
  td: ({ children }: React.PropsWithChildren) => <td className="border border-white/10 px-3 py-1.5 align-top">{children}</td>,
  hr: () => <hr className="my-4 border-white/10" />,
} satisfies React.ComponentProps<typeof Markdown>['components'];

export default function AssistantMarkdownContent({
  content,
  className,
}: AssistantMarkdownContentProps) {
  return (
    <div className={className}>
      <Markdown components={assistantMarkdownComponents} remarkPlugins={[remarkGfm]}>
        {content}
      </Markdown>
    </div>
  );
}
