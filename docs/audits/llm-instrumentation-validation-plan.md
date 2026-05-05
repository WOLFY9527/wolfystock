# LLM Instrumentation Validation Plan

Date: 2026-05-06
Mode: docs-only QA plan. No runtime behavior changed.

## 1. Purpose

This plan defines how to validate Phase 1A LLM instrumentation after implementation lands. It is a review and test plan only. It does not approve runtime changes, counters, tests, APIs, cache behavior, UI, prompt changes, model routing changes, provider changes, or live-provider validation.

This plan was prepared from clean documentation context. `docs/audits/llm-provider-duplicate-cost-metrics-design.md` and the likely implementation files were dirty during this pass, so they were not opened for this docs-only task.

## 2. Expected event coverage

Phase 1A should emit only privacy-safe, non-blocking observation events around existing LLM behavior.

| Event | Expected emission scenario | Behavior guard | Privacy guard |
| --- | --- | --- | --- |
| `llm_call_started` | Immediately before an existing LLM call attempt is made. | Must not change prompt construction, model selection, provider selection, retry count, timeout, fallback order, or call arguments. | Must not include raw prompt, messages, images, provider payloads, API keys, URLs with query strings, or full user/session ids. |
| `llm_call_completed` | After an existing LLM call attempt succeeds and returns through the current success path. | Must not change response parsing, usage accounting, integrity checks, report shape, or downstream persistence. | Labels must stay bounded; token and duration values should be bucketed when exposed as metric labels. |
| `llm_call_failed` | After an existing LLM call attempt fails on the same path that already handled failure. | Must preserve the original exception/failure behavior and fallback eligibility. | Must not emit raw stack traces, raw provider error bodies, raw response bodies, or secret-bearing config. |
| `llm_fallback_attempt` | When current behavior moves from one model/provider attempt to a fallback attempt. | Must not add, remove, reorder, or skip fallback attempts. | Must expose only bounded provider/model-family or redacted model-alias labels. |
| `llm_integrity_retry` | When current report integrity logic triggers its existing retry path. | Must not change integrity retry conditions, retry prompt construction, retry count, parser/schema semantics, or final failure behavior. | Retry reason must be a bounded bucket, not missing-field payloads or previous model output. |
| `llm_usage_persisted` | Only if implemented after existing usage persistence succeeds. | Must not change usage persistence inputs, success/failure handling, or transaction behavior. | Must not include raw prompt, response body, full stock/user/session identity, or secret model/provider config. |

## 3. Privacy validation checklist

Review captured events, logs, metrics, and test fixtures to confirm no metric/log label includes:

- raw prompt
- raw messages or conversation text
- raw image bytes, base64, data URL, OCR text, or uploaded image payload
- raw news or provider payloads
- API keys, tokens, Authorization headers, cookies, webhook URLs, or secret config values
- base URL query strings or credential-bearing URLs
- raw stack traces
- raw response bodies
- full user ids, owner ids, account ids, session ids, guest session ids, or request ids when avoidable
- secret channel names or private routing names
- unbounded exception text, provider reason text, or model output text

Expected safe labels include:

- `call_type`
- `model_family` or `model_alias` after redaction
- bounded `provider`
- `attempt_index`
- `fallback_depth`
- `retry_reason` bucket
- `outcome`
- `duration_bucket`
- `token_bucket` if already available from existing accounting
- `cache_key_hash` or input hash only when the hash is explicitly safe, salted where needed, and not reversible through returned metadata

## 4. Non-blocking behavior validation

Required behavior:

- metric helper failure must be swallowed
- original LLM success path must still succeed
- original LLM failure path must still fail the same way
- fallback order must remain unchanged
- fallback eligibility and stopping conditions must remain unchanged
- retry count must remain unchanged
- integrity retry behavior must remain unchanged
- usage persistence behavior must remain unchanged except additional non-blocking observation if implemented
- parser, schema, report integrity, and report output semantics must remain unchanged
- no new external network call, live LLM call, provider call, cache mutation, or execution-log mutation may be introduced by instrumentation

## 5. Suggested synthetic tests

Future implementation should use synthetic and mocked tests only. Do not call live LLMs or external providers.

- sanitizer strips or buckets unsafe labels
- sanitizer rejects or redacts raw prompts, messages, image payloads, provider payloads, secret values, raw URLs, stack traces, and response bodies
- metric emit helper swallows exceptions
- success path emits `llm_call_started` and `llm_call_completed`
- failure path emits `llm_call_started` and `llm_call_failed`
- fallback path emits `llm_fallback_attempt` without changing model order
- integrity retry path emits `llm_integrity_retry` without changing retry prompt or retry behavior
- `llm_usage_persisted` emits only after existing usage persistence succeeds, if that event is implemented
- no raw prompt, message, provider payload, image payload, response body, API key, token, or full user/session id appears in captured events
- metric failures do not mask original success or alter original failure

## 6. Manual review checklist

Review the implementation diff before running deeper checks:

- git diff is limited to intended backend instrumentation helper, call-site wiring, and focused tests
- event names match the approved design docs and this plan
- labels are bounded, redacted, and low cardinality
- no API response shape changes
- no prompt, model, fallback, retry, parser, schema, or integrity logic changes
- no external network calls added
- no dependency additions
- no frontend changes
- no provider runtime changes
- no `MarketCache` behavior changes
- no scanner, backtest, portfolio, notification, or DuckDB runtime changes
- no test fixtures contain real prompts, provider payloads, secrets, or user/session identifiers
- implementation keeps metrics best-effort and non-blocking

## 7. Recommended commands after implementation

Run deterministic checks only, with live-provider and live-LLM tests disabled:

```bash
python -m py_compile <touched_backend_files>
python -m pytest <focused_instrumentation_helper_tests>
python -m pytest <focused_analyzer_mocked_llm_tests_if_present>
rg -n "prompt|messages|data:image|Authorization|api[_-]?key|token|response_body|stack trace|traceback|session_id|guest_session" <touched_files>
./scripts/ci_gate.sh
```

Use `./scripts/ci_gate.sh` only when the repo state allows a broader gate without mixing unrelated concurrent work. Do not run live LLM, live provider, browser, cache refresh, or connectivity-probe tests for Phase 1A validation.

## 8. Acceptance criteria

The implementation is acceptable only if:

- LLM behavior is unchanged
- prompt, model route, fallback order, retry count, integrity retry, parser/schema semantics, and usage persistence behavior are unchanged
- privacy labels are safe, bounded, and redacted
- tests are synthetic/mocked and passing
- metric helper failures are non-blocking
- no live LLM or external-provider traffic is used for validation
- no dependencies are added
- no frontend, API, cache, provider runtime, scanner, backtest, portfolio, notification, or DuckDB behavior is changed
- final git status is clean except explicitly reported unrelated files from concurrent tasks

## 9. Follow-up sequence

After Phase 1A passes:

1. Provider fallback counters Phase 1B
2. MarketCache counters Phase 1C
3. Scanner AI duplicate candidate counter Phase 1D
4. Backend duplicate-cost summary API
5. Cache prototypes only after measurement

