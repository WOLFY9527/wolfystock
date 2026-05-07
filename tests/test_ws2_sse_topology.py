# -*- coding: utf-8 -*-
"""WS2 SSE topology evidence for multi-instance readiness."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from src.services.task_queue import AnalysisTaskQueue


class Ws2SseTopologyTestCase(unittest.TestCase):
    def tearDown(self) -> None:
        queue = AnalysisTaskQueue._instance
        if queue is not None:
            executor = getattr(queue, "_executor", None)
            if executor is not None and hasattr(executor, "shutdown"):
                executor.shutdown(wait=False, cancel_futures=True)
        AnalysisTaskQueue._instance = None

    def test_runtime_status_documents_process_local_sse_and_polling_fallback(self) -> None:
        queue = AnalysisTaskQueue(max_workers=1)

        with patch.dict("os.environ", {"WEB_CONCURRENCY": "2"}, clear=False):
            status = queue.get_runtime_status()

        streaming = status["streaming_topology"]
        self.assertEqual(status["mode"], "process_local")
        self.assertFalse(status["topology_ok"])
        self.assertEqual(status["launch_status"], "blocked_process_local_sse")
        self.assertEqual(streaming["sse_scope"], "process_local")
        self.assertFalse(streaming["sse_multi_instance_broadcast_safe"])
        self.assertEqual(streaming["safe_cross_instance_fallback"], "durable_task_polling")
        self.assertTrue(streaming["polling_cross_instance_safe"])
        self.assertFalse(streaming["external_service_required_by_default"])
        self.assertFalse(streaming["accepted_distributed_streaming_evidence"])
        self.assertIn("process-local", streaming["limitation"])
        self.assertIn("polling", streaming["fallback_guidance"])

    def test_runtime_status_topology_evidence_is_sanitized(self) -> None:
        queue = AnalysisTaskQueue(max_workers=1)

        with patch.dict("os.environ", {"WEB_CONCURRENCY": "2", "TOKEN": "not-a-real-token"}, clear=False):
            status = queue.get_runtime_status()
        serialized = json.dumps(status, ensure_ascii=False).lower()

        for forbidden in (
            "not-a-real-token",
            "api_key",
            "cookie",
            "session_id",
            "traceback",
            "stack trace",
            "raw_provider_payload",
            "provider_response",
            "debug_schema",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_single_process_status_remains_limited_until_distributed_streaming_evidence_exists(self) -> None:
        queue = AnalysisTaskQueue(max_workers=1)

        with patch.dict("os.environ", {}, clear=True):
            status = queue.get_runtime_status()

        self.assertTrue(status["topology_ok"])
        self.assertEqual(status["launch_status"], "limited_single_process")
        self.assertFalse(status["streaming_topology"]["accepted_distributed_streaming_evidence"])
        self.assertFalse(status["streaming_topology"]["sse_multi_instance_broadcast_safe"])


if __name__ == "__main__":
    unittest.main()
