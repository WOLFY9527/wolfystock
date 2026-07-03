export type ConsumerRawLeakageHit = {
  pattern: string;
  match: string;
  context: string;
};

export type ConsumerRawLeakageGuardOptions = {
  allowedPhrases?: readonly string[];
  extraForbiddenPatterns?: readonly RegExp[];
};

const defaultForbiddenPatterns = [
  /\bscore_contribution_not_allowed\b/i,
  /\bproviderRuntime\b/,
  /\bsourceAuthorityAllowed\b/,
  /\bscoreContributionAllowed\b/,
  /\brouteRejected\b/,
  /\bfallback_used\b/i,
  /\bproviderRuntimeChanged\b/,
  /\bsourceAuthorityRouteRejected\b/,
  /\brouteRejectedReasonCodes\b/,
  /\bsourceMetadata\b/,
  /\bcoverageDiagnostics\b/,
  /\badminDiagnostics\b/,
  /\brawProviderPayload\b/,
  /\bproviderRoute\b/,
  /\bdebugRef\b/,
  /\b[a-z]+(?:_[a-z0-9]+)+\b/,
  /\/api\/v\d+\/[^\s<>"']+/i,
  /\bsource-provenance:[^\s<]+/i,
  /\bmarket:(?:liquidity|marketregime|rotation|scanner|overview|temperature)[^\s<]*/i,
  /\bsynthetic_(?:provider_url|cache_key|request_id|debug_reason|score_trace|diagnostic_window|provider_payload_label)\b/i,
  /\bprovider\.example\b/i,
  /\breq-(?:scanner-raw|synth)-[a-z0-9-]+\b/i,
  /\b(?:traceback|stack trace)\b/i,
  /\braw\s+(?:payload|response|json|provider\s+payload)\b/i,
  /\bprovider\s+(?:runtime|trace|payload|debug|route)\b/i,
  /\b(?:research|evidence|data|scanner|watchlist|single[-\s]?stock)?\s*packet\b/i,
  /\bhandoff\b/i,
  /\bclean research handoff\b/i,
  /\bevidence\s+famil(?:y|ies)\b/i,
  /\bmissing or incomplete evidence families\b/i,
  /\bbusiness-quality review\b/i,
  /\bOBSERVATION-ONLY\b/,
  /\bNo verified local peer group metadata\b/i,
  /\bpeer group metadata\b/i,
  /\bLoad recent local daily OHLCV\b/i,
  /\bhistorical\s+ohlcv\b/i,
  /\bquote\s+snapshot\b/i,
  /\buniverse\b/i,
  /\bprovider\s+error\b/i,
  /\bdebug\b/i,
  /\bdry[-\s]?run\b/i,
  /\bpipeline\b/i,
  /\bObservation-only research readiness; not personalized financial advice\b/i,
  /\bObserve whether downside volume pressure fades or remains persistent\b/i,
  /\bNo portfolio exposure available\b/i,
  /\bevidence limited\b/i,
  /数据不足(?:[\s\S]{0,80}数据不足){2}/,
] as const;

function stripAllowedPhrases(text: string, allowedPhrases: readonly string[]) {
  return allowedPhrases.reduce((current, phrase) => current.replaceAll(phrase, ''), text);
}

function buildContext(text: string, index: number, match: string) {
  const start = Math.max(0, index - 24);
  const end = Math.min(text.length, index + match.length + 24);
  return text.slice(start, end).replace(/\s+/g, ' ').trim();
}

export function findConsumerRawLeakage(
  text: string,
  options: ConsumerRawLeakageGuardOptions = {},
): ConsumerRawLeakageHit[] {
  const sanitizedText = stripAllowedPhrases(text, options.allowedPhrases ?? []);
  const forbiddenPatterns = [...defaultForbiddenPatterns, ...(options.extraForbiddenPatterns ?? [])];
  const hits: ConsumerRawLeakageHit[] = [];

  for (const pattern of forbiddenPatterns) {
    const match = sanitizedText.match(pattern);
    if (!match || match.index == null) {
      continue;
    }
    hits.push({
      pattern: pattern.toString(),
      match: match[0],
      context: buildContext(sanitizedText, match.index, match[0]),
    });
  }

  return hits;
}

export function getConsumerRawLeakagePatterns() {
  return [...defaultForbiddenPatterns];
}

export function textContentWithoutObservationBoundary(root: HTMLElement): string {
  const clone = root.cloneNode(true) as HTMLElement;
  clone.querySelectorAll('[data-testid="observation-only-boundary"], [data-testid="backtest-research-boundary"]')
    .forEach((node) => node.remove());
  return clone.textContent || '';
}
