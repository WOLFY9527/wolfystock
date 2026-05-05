# -*- coding: utf-8 -*-
"""Tests for the scanner AI interpretation layer."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from src.core.scanner_profile import CN_A_PREOPEN_V1, US_PREOPEN_V1
from src.services.llm_instrumentation import (
    reset_llm_event_counters,
    set_llm_event_sink,
    snapshot_llm_event_counters,
)
from src.services.scanner_ai_service import ScannerAiInterpretationService


class FakeAnalyzer:
    def __init__(self, responses: list[dict | None], *, available: bool = True) -> None:
        self._responses = list(responses)
        self._available = available

    def is_available(self) -> bool:
        return self._available

    def generate_text_with_meta(self, *args, **kwargs):  # noqa: ANN002, ANN003
        _ = args, kwargs
        if not self._responses:
            return None
        return self._responses.pop(0)


def _candidate(symbol: str, rank: int) -> dict:
    return {
        "symbol": symbol,
        "name": f"股票{symbol}",
        "rank": rank,
        "score": 85.0 - rank,
        "quality_hint": "高优先级",
        "reason_summary": "趋势和量能结构较好。",
        "reasons": ["趋势结构完整。", "量能活跃。"],
        "risk_notes": ["需要确认竞价承接。"],
        "watch_context": [{"label": "观察触发", "value": "关注前高突破。"}],
        "boards": ["AI算力"],
        "key_metrics": [{"label": "最新价", "value": "18.20"}],
        "feature_signals": [{"label": "趋势结构", "value": "18.0 / 20"}],
        "_diagnostics": {},
    }


class ScannerAiInterpretationServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        reset_llm_event_counters()
        set_llm_event_sink(None)

    def tearDown(self) -> None:
        set_llm_event_sink(None)
        reset_llm_event_counters()

    def test_interpret_shortlist_generates_top_n_and_skips_tail(self) -> None:
        analyzer = FakeAnalyzer(
            [
                {
                    "text": (
                        '{"summary":"更像趋势延续里的临界突破观察。","opportunity_type":"临界突破",'
                        '"risk_interpretation":"高开过多时要防冲高回落。","watch_plan":"先看竞价承接，再看开盘量能是否继续放大。",'
                        '"review_commentary":null}'
                    ),
                    "model": "gemini/gemini-2.5-flash",
                    "provider": "gemini",
                    "usage": {},
                    "attempt_trace": [],
                },
                {
                    "text": (
                        '{"summary":"板块联动还在，但更适合等确认。","opportunity_type":"板块联动",'
                        '"risk_interpretation":"若板块强度转弱，个股延续性会下降。","watch_plan":"先看板块同步性，再看个股量比是否维持强势。",'
                        '"review_commentary":null}'
                    ),
                    "model": "gemini/gemini-2.5-flash",
                    "provider": "gemini",
                    "usage": {},
                    "attempt_trace": [],
                },
            ]
        )
        service = ScannerAiInterpretationService(
            config=SimpleNamespace(
                scanner_ai_enabled=True,
                scanner_ai_top_n=2,
                litellm_model="gemini/gemini-2.5-flash",
            ),
            analyzer_factory=lambda: analyzer,
        )

        candidates, diagnostics = service.interpret_shortlist(
            profile=CN_A_PREOPEN_V1,
            candidates=[_candidate("600001", 1), _candidate("600002", 2), _candidate("600003", 3)],
        )

        self.assertEqual(diagnostics["status"], "completed")
        self.assertEqual(diagnostics["generated_candidates"], 2)
        self.assertTrue(candidates[0]["ai_interpretation"]["available"])
        self.assertEqual(candidates[0]["ai_interpretation"]["opportunity_type"], "临界突破")
        self.assertEqual(candidates[1]["ai_interpretation"]["status"], "generated")
        self.assertEqual(candidates[2]["ai_interpretation"]["status"], "skipped")

        events = snapshot_llm_event_counters()
        event_names = [entry["event"] for entry in events]
        self.assertEqual(event_names.count("scanner_ai_duplicate_candidate_observed"), 2)
        self.assertEqual(event_names.count("scanner_ai_interpretation_started"), 2)
        self.assertEqual(event_names.count("scanner_ai_interpretation_completed"), 2)
        self.assertEqual(event_names.count("scanner_ai_interpretation_skipped"), 1)
        completed = [entry for entry in events if entry["event"] == "scanner_ai_interpretation_completed"]
        self.assertTrue(all(entry["labels"]["outcome"] == "generated" for entry in completed))
        self.assertTrue(all(entry["labels"]["model_family"] == "gemini/gemini-2.5" for entry in completed))
        emitted_label_text = repr(events)
        self.assertNotIn("600001", emitted_label_text)
        self.assertNotIn("600002", emitted_label_text)
        self.assertNotIn("600003", emitted_label_text)

    def test_interpret_shortlist_returns_unavailable_when_analyzer_is_not_ready(self) -> None:
        service = ScannerAiInterpretationService(
            config=SimpleNamespace(
                scanner_ai_enabled=True,
                scanner_ai_top_n=2,
                litellm_model="gemini/gemini-2.5-flash",
            ),
            analyzer_factory=lambda: FakeAnalyzer([], available=False),
        )

        candidates, diagnostics = service.interpret_shortlist(
            profile=CN_A_PREOPEN_V1,
            candidates=[_candidate("600001", 1), _candidate("600002", 2)],
        )

        self.assertEqual(diagnostics["status"], "unavailable")
        self.assertTrue(all(item["ai_interpretation"]["status"] == "unavailable" for item in candidates))
        events = snapshot_llm_event_counters()
        self.assertEqual([entry["event"] for entry in events], ["scanner_ai_interpretation_skipped"])
        self.assertEqual(events[0]["labels"]["skip_reason"], "unavailable")

    def test_interpret_shortlist_emits_skipped_for_disabled_and_non_cn(self) -> None:
        disabled_service = ScannerAiInterpretationService(
            config=SimpleNamespace(
                scanner_ai_enabled=False,
                scanner_ai_top_n=2,
                litellm_model="gemini/gemini-2.5-flash",
            ),
            analyzer_factory=lambda: FakeAnalyzer([]),
        )

        disabled_candidates, disabled_diagnostics = disabled_service.interpret_shortlist(
            profile=CN_A_PREOPEN_V1,
            candidates=[_candidate("600001", 1), _candidate("600002", 2)],
        )

        self.assertEqual(disabled_diagnostics["status"], "disabled")
        self.assertTrue(all(item["ai_interpretation"]["status"] == "disabled" for item in disabled_candidates))
        events = snapshot_llm_event_counters()
        self.assertEqual([entry["event"] for entry in events], ["scanner_ai_interpretation_skipped"])
        self.assertEqual(events[0]["labels"]["skip_reason"], "disabled")

        reset_llm_event_counters()
        non_cn_service = ScannerAiInterpretationService(
            config=SimpleNamespace(
                scanner_ai_enabled=True,
                scanner_ai_top_n=2,
                litellm_model="gemini/gemini-2.5-flash",
            ),
            analyzer_factory=lambda: FakeAnalyzer([]),
        )

        non_cn_candidates, non_cn_diagnostics = non_cn_service.interpret_shortlist(
            profile=US_PREOPEN_V1,
            candidates=[_candidate("AAPL", 1), _candidate("MSFT", 2)],
        )

        self.assertEqual(non_cn_diagnostics["status"], "skipped")
        self.assertTrue(all(item["ai_interpretation"]["status"] == "skipped" for item in non_cn_candidates))
        events = snapshot_llm_event_counters()
        self.assertEqual([entry["event"] for entry in events], ["scanner_ai_interpretation_skipped"])
        self.assertEqual(events[0]["labels"]["skip_reason"], "non_cn")

    def test_duplicate_candidate_observed_uses_stable_safe_hash(self) -> None:
        analyzer = FakeAnalyzer(
            [
                {
                    "text": (
                        '{"summary":"更像趋势延续里的临界突破观察。","opportunity_type":"临界突破",'
                        '"risk_interpretation":"高开过多时要防冲高回落。","watch_plan":"先看竞价承接，再看开盘量能是否继续放大。",'
                        '"review_commentary":null}'
                    ),
                    "model": "gemini/gemini-2.5-flash",
                    "provider": "gemini",
                    "usage": {},
                    "attempt_trace": [],
                },
                {
                    "text": (
                        '{"summary":"更像趋势延续里的临界突破观察。","opportunity_type":"临界突破",'
                        '"risk_interpretation":"高开过多时要防冲高回落。","watch_plan":"先看竞价承接，再看开盘量能是否继续放大。",'
                        '"review_commentary":null}'
                    ),
                    "model": "gemini/gemini-2.5-flash",
                    "provider": "gemini",
                    "usage": {},
                    "attempt_trace": [],
                },
            ]
        )
        service = ScannerAiInterpretationService(
            config=SimpleNamespace(
                scanner_ai_enabled=True,
                scanner_ai_top_n=1,
                litellm_model="gemini/gemini-2.5-flash",
            ),
            analyzer_factory=lambda: analyzer,
        )
        candidate = _candidate("600001", 1)

        service.interpret_shortlist(profile=CN_A_PREOPEN_V1, candidates=[candidate])
        service.interpret_shortlist(profile=CN_A_PREOPEN_V1, candidates=[candidate])

        duplicate_events = [
            entry for entry in snapshot_llm_event_counters() if entry["event"] == "scanner_ai_duplicate_candidate_observed"
        ]
        self.assertEqual(len(duplicate_events), 1)
        self.assertEqual(duplicate_events[0]["count"], 2)
        candidate_hash = duplicate_events[0]["labels"]["candidate_hash"]
        self.assertRegex(candidate_hash, r"^[a-f0-9]{16}$")
        self.assertNotEqual(candidate_hash, "600001")

    def test_metric_sink_failure_does_not_change_candidate_output(self) -> None:
        response = {
            "text": (
                '{"summary":"更像趋势延续里的临界突破观察。","opportunity_type":"临界突破",'
                '"risk_interpretation":"高开过多时要防冲高回落。","watch_plan":"先看竞价承接，再看开盘量能是否继续放大。",'
                '"review_commentary":null}'
            ),
            "model": "gemini/gemini-2.5-flash",
            "provider": "gemini",
            "usage": {},
            "attempt_trace": [],
        }
        config = SimpleNamespace(
            scanner_ai_enabled=True,
            scanner_ai_top_n=1,
            litellm_model="gemini/gemini-2.5-flash",
        )
        baseline_service = ScannerAiInterpretationService(
            config=config,
            analyzer_factory=lambda: FakeAnalyzer([dict(response)]),
        )
        baseline_candidates, baseline_diagnostics = baseline_service.interpret_shortlist(
            profile=CN_A_PREOPEN_V1,
            candidates=[_candidate("600001", 1)],
        )

        reset_llm_event_counters()

        def failing_sink(event_name: str, labels: dict[str, str]) -> None:
            _ = event_name, labels
            raise RuntimeError("metrics unavailable")

        set_llm_event_sink(failing_sink)
        instrumented_service = ScannerAiInterpretationService(
            config=config,
            analyzer_factory=lambda: FakeAnalyzer([dict(response)]),
        )
        instrumented_candidates, instrumented_diagnostics = instrumented_service.interpret_shortlist(
            profile=CN_A_PREOPEN_V1,
            candidates=[_candidate("600001", 1)],
        )

        self.assertEqual(instrumented_diagnostics["status"], baseline_diagnostics["status"])
        self.assertEqual(instrumented_diagnostics["generated_candidates"], baseline_diagnostics["generated_candidates"])
        self.assertEqual(instrumented_candidates[0]["symbol"], baseline_candidates[0]["symbol"])
        self.assertEqual(instrumented_candidates[0]["rank"], baseline_candidates[0]["rank"])
        self.assertEqual(instrumented_candidates[0]["score"], baseline_candidates[0]["score"])
        self.assertEqual(instrumented_candidates[0]["reason_summary"], baseline_candidates[0]["reason_summary"])
        self.assertEqual(instrumented_candidates[0]["ai_interpretation"]["status"], baseline_candidates[0]["ai_interpretation"]["status"])
        self.assertEqual(
            instrumented_candidates[0]["ai_interpretation"]["opportunity_type"],
            baseline_candidates[0]["ai_interpretation"]["opportunity_type"],
        )

    def test_enrich_review_commentary_updates_existing_generated_payload(self) -> None:
        analyzer = FakeAnalyzer(
            [
                {
                    "text": '{"review_commentary":"后续表现跑赢基准，说明趋势与量能配合有效。"}',
                    "model": "gemini/gemini-2.5-flash",
                    "provider": "gemini",
                    "usage": {},
                    "attempt_trace": [],
                }
            ]
        )
        service = ScannerAiInterpretationService(
            config=SimpleNamespace(
                scanner_ai_enabled=True,
                scanner_ai_top_n=2,
                litellm_model="gemini/gemini-2.5-flash",
            ),
            analyzer_factory=lambda: analyzer,
        )
        candidate = _candidate("600001", 1)
        candidate["diagnostics"] = {
            "ai_interpretation": {
                "status": "generated",
                "summary": "更像趋势延续里的临界突破观察。",
                "opportunity_type": "临界突破",
                "risk_interpretation": "高开过多时要防冲高回落。",
                "watch_plan": "先看竞价承接，再看开盘量能是否继续放大。",
                "review_commentary": None,
                "review_commentary_status": "pending_review_data",
            }
        }

        updated = service.enrich_review_commentary(
            profile=CN_A_PREOPEN_V1,
            candidate=candidate,
            realized_outcome={
                "review_status": "ready",
                "review_window_return_pct": 5.6,
                "max_favorable_move_pct": 7.4,
                "max_adverse_move_pct": -1.5,
                "outperformed_benchmark": True,
                "thesis_match": "validated",
            },
        )

        self.assertIsNotNone(updated)
        self.assertEqual(updated["review_commentary_status"], "generated")
        self.assertIn("跑赢基准", updated["review_commentary"])


if __name__ == "__main__":
    unittest.main()
