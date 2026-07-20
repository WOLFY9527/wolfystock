# Data Trust And Protected Semantics

> Status: Canonical
> Scope: evidence truth, source authority, readiness, no-advice, and protected financial-domain semantics
> Audience: backend, frontend, provider, scanner, backtest, portfolio, and review work

Authorization to change a protected domain comes only from the current task and
[`AGENTS.md`](../../AGENTS.md). This document defines the vocabulary and
cross-domain distinctions that implementations and consumer projections must
preserve.

## Truth Distinctions

The following states are not interchangeable:

| State | Must remain distinct from |
| --- | --- |
| unavailable | zero or neutral |
| missing | neutral, empty, or successful |
| stale | fresh |
| delayed | live |
| proxy | official |
| synthetic | real |
| fixture | production |
| cached | live or current without timestamp proof |
| fallback | primary or authoritative |
| inferred | observed |
| not checked | ready |
| skipped | passed |
| not evaluated | passed |
| corrupt state | empty state |
| injected transport | live transport |
| task accepted | analysis completed |
| generated | canonical source |
| historical | current policy |
| temporary evidence | durable documentation |
| document present | document authoritative |

Missing evidence stays missing. Do not fabricate or coerce quote,
fundamental, filing, event, IV, Greek, bid/ask, OI, volume, FX, benchmark,
freshness, or lineage values to complete a payload or layout.

## Provider And Source Authority

Provider runtime owns provider order, fallback, retry/circuit behavior,
deadlines, freshness labels, source authority, display rights, optional
enrichment budgets, sanitized diagnostics, and cache/local-first behavior.
Changing any of these requires explicit protected-domain scope.

Fallback, cached, proxy, repaired, inferred, fixture, synthetic, dry-run,
parser-only, request-supplied, and observation-only data remain visibly
non-live and non-authoritative. Raw provider payloads do not cross into public
API or consumer presentation contracts.

### Provenance vocabulary guard

The following fields are not interchangeable and must not be used as aliases
for one another: `diagnosticOnly`, `observationOnly`, `authorityGrant`,
`sourceAuthorityAllowed`, `scoreContributionAllowed`,
`scoreReliabilityAllowed`, `score_grade_allowed`,
`scoreGradeEvidenceAllowed`, `freshness`, `stale`, `partial`, and `fallback`.

A diagnostic or observation field grants no source, score, routing, live-call,
or decision authority. Freshness describes evidence condition; stale, partial,
and fallback evidence remains visible but cannot be silently promoted.

## Data Family Readiness

| Data family | Current boundary |
| --- | --- |
| Official risk and volatility | Partial until VIX/volatility, rates, Fed liquidity, credit stress, and official macro rows have source authority. |
| Authorized quote spine | Partial until US/CN/HK quotes and OHLCV have durable lineage, freshness, and display authority. |
| Index/ETF membership | Partial until membership and weighting are official rather than proxy-only. |
| Scanner universe/history | Partial until universe, local history, quote freshness, turnover, and evidence packets pass their gates. |
| Fundamentals/filings/events | Partial; missing ratios, filings, catalysts, events, or peers remain missing. |
| Options chains/Greeks | Blocked or observation-only without entitlement, redisplay rights, methodology, and chain/Greek completeness. |
| Scenario baselines | Partial until durable baseline snapshots and target-environment evidence exist. |
| Backtest lineage | Research-useful but partial until adjusted basis, calendar, PIT universe, reproducibility, and stored-result authority are proven. |
| Factor research lineage | Diagnostic-only without PIT universe and factor-return contracts. |
| Portfolio price/FX lineage | Partial; valuation credibility is bounded by quote, FX, timestamp, source, and ledger provenance. |

## Domain Contracts

### Market, Liquidity, And Rotation

Market context may show bounded observations, but proxy breadth or
quote-derived approximations cannot become official or score-grade
institutional claims. Observation time, source time, and lifecycle time are
separate facts.

### Scanner

Scanner score contributions, filters, thresholds, ordering, universe,
live/fallback labels, comparable-run readiness, and stored run semantics are
protected. A candidate is a research-priority signal, not a recommendation.

### Options

Options Lab is a read-only research console, not execution, strategy ranking,
or order entry. Fixture/dry-run providers and disabled live stubs fail closed
until entitlement, redisplay, chain, Greeks, IV, OI, volume, and methodology
evidence are proven.

### Scenario

Scenario Lab compares bounded shocks. Request-supplied, fallback, static,
sample, or stale baselines remain observation-only and do not imply execution
readiness.

### Backtest

Backtest owns deterministic rule evaluation, fills, costs, metrics, benchmark
semantics, parameter and winner meaning, universe, stored-result readback,
exports, and comparison workflows. A stored result is not replaceable by a
new live computation or a fallback payload without explicit versioned
semantics.

### Portfolio

Portfolio owns accounts, holdings, cash, transactions, P&L, FX/native currency,
cost basis, broker sync/import overlays, ledger mutations, and owner-isolated
read projections. UI and reporting code must not recalculate accounting
authority or imply broker order execution.

### Auth And Admin Evidence

Auth, RBAC, sessions, cookies, CSRF/CORS, MFA, owner isolation, and admin
protection fail closed. Admin diagnostics may expose bounded internal state to
authorized operators, but never raw credentials, security material, provider
payloads, or unrestricted local paths.

## Consumer Projection

Consumer copy communicates the visible state and a bounded explanation. It
does not expose raw provider, routing, scoring, schema, or cache fields.

| Surface | State | Consumer message |
| --- | --- | --- |
| Market Overview | `AVAILABLE` | No additional headline. |
| Liquidity | `PARTIAL` | 部分数据暂不可用。 |
| Scanner | `INSUFFICIENT` | 当前信号置信度较低，仅供观察。 |
| Portfolio | `DELAYED` | 已使用最近一次可用数据。 |
| Backtest | `UNAVAILABLE` | 本模块暂不可用，请稍后重试。 |

Consumer pages must not expose internal enums such as `provider_missing`,
`sourceClass`, `contractVersion`, `failClosed`, raw lineage JSON, or provider
routing decisions. Map them through the existing consumer presentation owner;
do not add a second mapper in a page.

## No-Advice Boundary

WolfyStock organizes evidence and supports research. It does not provide
buy/sell/hold instructions, target prices, stop-loss instructions, position
sizing, or add/reduce-position recommendations. User-visible conclusions must
stay analytical, disclose evidence limits, and describe what to inspect next.

## Readiness Roadmap

The roadmap is not a claim that a capability is live. The durable order is:

1. Official volatility and macro/rates/liquidity source authority.
2. Authorized US/CN/HK quote spine with lineage, freshness, and display rights.
3. Index/ETF quote coverage and membership/weight proof.
4. Scanner universe, history, turnover, and quote-readiness gates.
5. Watchlist and single-stock research packet completeness.
6. Portfolio price and FX lineage.
7. Options entitlement, redisplay rights, and methodology proof.
8. Scenario durable baselines and target-environment evidence.
9. Backtest dataset lineage, adjusted basis, calendar, PIT universe, and reproducibility.
10. Factor research lineage with PIT membership and return contracts.

Every step must expose blocked, partial, missing, unauthorized, stale, or
observation-only states instead of hiding them behind positive copy.
