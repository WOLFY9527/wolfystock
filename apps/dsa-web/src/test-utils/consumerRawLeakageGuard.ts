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
