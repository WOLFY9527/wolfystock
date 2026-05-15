# -*- coding: utf-8 -*-
"""Focused observability tests for Home analysis pipeline timings."""

from __future__ import annotations

import time
import unittest

from src.core.pipeline import StockAnalysisPipeline


class PipelineAnalysisObservabilityTestCase(unittest.TestCase):
    def test_log_home_analysis_stage_sanitizes_status_metadata(self) -> None:
        started_at = time.perf_counter() - 0.01

        with self.assertLogs("src.core.pipeline", level="INFO") as captured:
            StockAnalysisPipeline._log_home_analysis_stage(
                symbol="ORCL",
                stage_name="llm_call",
                started_at=started_at,
                status="timeout token=sk-secret",
            )

        line = "\n".join(captured.output)
        self.assertIn("stage=llm_call", line)
        self.assertIn("symbol=ORCL", line)
        self.assertIn("elapsed_ms=", line)
        self.assertIn("status=unknown", line)
        self.assertNotIn("sk-secret", line)


if __name__ == "__main__":
    unittest.main()
