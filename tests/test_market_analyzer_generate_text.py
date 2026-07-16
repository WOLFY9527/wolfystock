# -*- coding: utf-8 -*-
"""Tests for Analyzer.generate_text() and the market_analyzer bypass fix.

Covers:
- generate_text() returns the LLM response on success
- generate_text() returns None and logs on failure (no exception propagated)
- market_analyzer calls generate_text(), not private analyzer attributes
- Any provider configuration (Gemini / Anthropic / OpenAI / LLM_CHANNELS)
  does NOT trigger AttributeError (regression guard for the old bypass bug)
"""
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# Stub heavy dependencies before project imports
for _mod in ("litellm", "google.generativeai", "google.genai", "anthropic"):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

import pytest
from unittest.mock import PropertyMock


# ---------------------------------------------------------------------------
# Analyzer.generate_text()
# ---------------------------------------------------------------------------

class TestAnalyzerGenerateText:
    def _make_analyzer(self):
        """Return a minimally configured GeminiAnalyzer with _call_litellm mocked."""
        with patch("src.analyzer.get_config") as mock_cfg:
            cfg = MagicMock()
            cfg.litellm_model = "gemini/gemini-2.0-flash"
            cfg.litellm_fallback_models = []
            cfg.gemini_api_keys = ["sk-gemini-testkey-1234"]
            cfg.anthropic_api_keys = []
            cfg.openai_api_keys = []
            cfg.deepseek_api_keys = []
            cfg.llm_model_list = []
            cfg.openai_base_url = None
            mock_cfg.return_value = cfg
            from src.analyzer import GeminiAnalyzer
            analyzer = GeminiAnalyzer.__new__(GeminiAnalyzer)
            analyzer._router = None
            return analyzer

    def test_generate_text_returns_llm_response(self):
        analyzer = self._make_analyzer()
        with patch.object(analyzer, "_call_litellm", return_value="市场分析报告") as mock_call:
            result = analyzer.generate_text("写一份复盘", max_tokens=1024, temperature=0.5)
            assert result == "市场分析报告"
            mock_call.assert_called_once_with(
                "写一份复盘",
                generation_config={"max_tokens": 1024, "temperature": 0.5},
                call_type="market_review",
            )

    def test_generate_text_returns_none_on_failure(self):
        analyzer = self._make_analyzer()
        with patch.object(analyzer, "_call_litellm", side_effect=Exception("LLM error")):
            result = analyzer.generate_text("prompt")
            assert result is None  # must not raise

    def test_generate_text_default_params(self):
        analyzer = self._make_analyzer()
        with patch.object(analyzer, "_call_litellm", return_value="ok") as mock_call:
            analyzer.generate_text("hello")
            _, kwargs = mock_call.call_args
            gen_cfg = kwargs["generation_config"]
            assert gen_cfg["max_tokens"] == 2048
            assert gen_cfg["temperature"] == 0.7
            assert kwargs["call_type"] == "market_review"

    def test_call_litellm_extracts_text_from_deepseek_v4_content_blocks(self):
        with patch("src.analyzer.get_config") as mock_cfg, \
             patch("src.analyzer.litellm.completion") as mock_completion, \
             patch("src.analyzer.emit_llm_event") as mock_event:
            cfg = MagicMock()
            cfg.litellm_model = "deepseek/deepseek-v4-pro"
            cfg.litellm_fallback_models = []
            cfg.gemini_api_keys = []
            cfg.anthropic_api_keys = []
            cfg.openai_api_keys = []
            cfg.deepseek_api_keys = ["sk-deepseek-testkey-1234"]
            cfg.llm_model_list = []
            cfg.openai_base_url = None
            mock_cfg.return_value = cfg

            from src.analyzer import GeminiAnalyzer

            analyzer = GeminiAnalyzer.__new__(GeminiAnalyzer)
            analyzer._router = None
            analyzer._litellm_available = True

            mock_completion.return_value = type(
                "MockResponse",
                (),
                {
                    "choices": [
                        type(
                            "Choice",
                            (),
                            {
                                "message": type(
                                    "Message",
                                    (),
                                    {
                                        "content": [
                                            {"type": "text", "text": "DeepSeek v4 says hello"},
                                        ],
                                    },
                                )(),
                            },
                        )(),
                    ],
                    "usage": type(
                        "Usage",
                        (),
                        {
                            "prompt_tokens": 10,
                            "completion_tokens": 12,
                            "total_tokens": 22,
                        },
                    )(),
                },
            )()

            text, model, usage, attempt_trace = analyzer._call_litellm(
                "Say hello",
                generation_config={"max_tokens": 64, "temperature": 0},
            )

            assert text == "DeepSeek v4 says hello"
            assert model == "deepseek/deepseek-v4-pro"
            assert usage["total_tokens"] == 22
            assert attempt_trace[-1]["result"] == "succeeded"
            emitted = [call.args[0] for call in mock_event.call_args_list]
            assert "llm_call_started" in emitted
            assert "llm_call_completed" in emitted

    def test_call_litellm_ignores_non_text_content_blocks(self):
        with patch("src.analyzer.get_config") as mock_cfg, \
             patch("src.analyzer.litellm.completion") as mock_completion, \
             patch("src.analyzer.emit_llm_event") as mock_event:
            cfg = MagicMock()
            cfg.litellm_model = "deepseek/deepseek-v4-pro"
            cfg.litellm_fallback_models = []
            cfg.gemini_api_keys = []
            cfg.anthropic_api_keys = []
            cfg.openai_api_keys = []
            cfg.deepseek_api_keys = ["sk-deepseek-testkey-1234"]
            cfg.llm_model_list = []
            cfg.openai_base_url = None
            mock_cfg.return_value = cfg

            from src.analyzer import GeminiAnalyzer

            analyzer = GeminiAnalyzer.__new__(GeminiAnalyzer)
            analyzer._router = None
            analyzer._litellm_available = True

            mock_completion.return_value = type(
                "MockResponse",
                (),
                {
                    "choices": [
                        type(
                            "Choice",
                            (),
                            {
                                "message": type(
                                    "Message",
                                    (),
                                    {
                                        "content": [
                                            {"type": "reasoning", "content": "internal scratchpad"},
                                            {"type": "text", "text": '{"summary":"final json"}'},
                                        ],
                                    },
                                )(),
                            },
                        )(),
                    ],
                    "usage": type(
                        "Usage",
                        (),
                        {
                            "prompt_tokens": 10,
                            "completion_tokens": 12,
                            "total_tokens": 22,
                        },
                    )(),
                },
            )()

            text, model, usage, attempt_trace = analyzer._call_litellm(
                "Return JSON",
                generation_config={"max_tokens": 64, "temperature": 0},
            )

            assert text == '{"summary":"final json"}'
            assert model == "deepseek/deepseek-v4-pro"
            assert usage["total_tokens"] == 22
            assert attempt_trace[-1]["result"] == "succeeded"
            emitted = [call.args[0] for call in mock_event.call_args_list]
            assert "llm_call_started" in emitted
            assert "llm_call_completed" in emitted


# ---------------------------------------------------------------------------
# market_analyzer uses generate_text(), not private attributes
# ---------------------------------------------------------------------------

class TestMarketAnalyzerBypassFix:
    def _make_market_analyzer_with_mock_generate_text(self, return_value="复盘报告"):
        """Return a MarketAnalyzer whose embedded Analyzer.generate_text is mocked."""
        from src.core.market_profile import CN_PROFILE
        from src.core.market_strategy import get_market_strategy_blueprint

        with patch("src.analyzer.get_config") as mock_cfg, \
             patch("src.market_analyzer.get_config") as mock_cfg2:
            cfg = MagicMock()
            cfg.litellm_model = "gemini/gemini-2.0-flash"
            cfg.litellm_fallback_models = []
            cfg.gemini_api_keys = ["sk-gemini-testkey-1234"]
            cfg.anthropic_api_keys = []
            cfg.openai_api_keys = []
            cfg.deepseek_api_keys = []
            cfg.llm_model_list = []
            cfg.openai_base_url = None
            cfg.market_review_region = "cn"
            mock_cfg.return_value = cfg
            mock_cfg2.return_value = cfg

            from src.analyzer import GeminiAnalyzer
            from src.market_analyzer import MarketAnalyzer

            analyzer = GeminiAnalyzer.__new__(GeminiAnalyzer)
            analyzer._router = None
            analyzer._litellm_available = True
            analyzer.generate_text = MagicMock(return_value=return_value)

            ma = MarketAnalyzer.__new__(MarketAnalyzer)
            ma.analyzer = analyzer
            ma.profile = CN_PROFILE
            ma.strategy = get_market_strategy_blueprint("cn")
            ma.region = "cn"
            return ma

    def test_no_access_to_private_model_attribute(self):
        """generate_text() must be called; _model must never be accessed."""
        ma = self._make_market_analyzer_with_mock_generate_text("复盘结果")
        # Ensure _model attribute does not exist (simulates PR #494 state)
        assert not hasattr(ma.analyzer, "_model") or ma.analyzer._model is None, (
            "_model should not be set on the LiteLLM-based analyzer"
        )
        # generate_text is a MagicMock, so calling it won't crash
        result = ma.analyzer.generate_text("prompt")
        assert result == "复盘结果"
        ma.analyzer.generate_text.assert_called_once()

    def test_generate_text_none_falls_back_to_template(self):
        """generate_market_review() falls back to template when generate_text returns None."""
        from src.market_analyzer import MarketOverview, MarketIndex

        ma = self._make_market_analyzer_with_mock_generate_text(return_value=None)
        overview = MarketOverview(
            date="2026-03-05",
            indices=[
                MarketIndex(
                    code="000001",
                    name="上证指数",
                    current=3300.0,
                    change=5.0,
                    change_pct=0.15,
                )
            ],
        )
        result = ma.generate_market_review(overview, [])
        assert isinstance(result, str) and len(result) > 0
        ma.analyzer.generate_text.assert_called_once()
        self._assert_market_index_preserves_missing_values_and_source_metadata()
        self._assert_market_reports_render_missing_unavailable_and_real_zero_flat()
        self._assert_market_template_treats_authoritative_zero_as_flat()

    def _assert_market_index_preserves_missing_values_and_source_metadata(self):
        ma = self._make_market_analyzer_with_mock_generate_text()
        ma.data_manager = SimpleNamespace(
            get_main_indices=lambda region: [
                {
                    "code": "000001",
                    "name": "上证指数",
                    "current": "bad",
                    "change": None,
                    "change_pct": None,
                    "open": None,
                    "high": None,
                    "low": None,
                    "prev_close": None,
                    "volume": None,
                    "amount": None,
                    "amplitude": None,
                    "source": "cached_fixture",
                    "observedAt": "2026-07-16T09:30:01+08:00",
                    "asOf": "2026-07-16T09:30:00+08:00",
                    "freshness": "cached",
                    "providerStatus": "partial",
                    "coverage": {"price": "missing"},
                    "isPartial": True,
                    "isProxy": True,
                    "isSynthetic": False,
                }
            ]
        )

        indices = ma._get_main_indices()

        assert len(indices) == 1
        index = indices[0]
        assert index.current is None
        assert index.change is None
        assert index.change_pct is None
        assert index.source == "cached_fixture"
        assert index.observed_at == "2026-07-16T09:30:01+08:00"
        assert index.as_of == "2026-07-16T09:30:00+08:00"
        assert index.freshness == "cached"
        assert index.provider_status == "partial"
        assert index.coverage == {"price": "missing"}
        assert index.is_partial is True
        assert index.is_proxy is True
        assert index.is_synthetic is False
        assert index.to_dict()["current"] is None
        assert index.to_dict()["freshness"] == "cached"

    def _assert_market_reports_render_missing_unavailable_and_real_zero_flat(self):
        from src.market_analyzer import MarketOverview, MarketIndex

        ma = self._make_market_analyzer_with_mock_generate_text()
        overview = MarketOverview(
            date="2026-07-16",
            indices=[
                MarketIndex(
                    code="000001",
                    name="上证指数",
                    current=None,
                    change=None,
                    change_pct=None,
                    amount=None,
                ),
                MarketIndex(
                    code="399001",
                    name="深证成指",
                    current=0.0,
                    change=0.0,
                    change_pct=0.0,
                    amount=0.0,
                ),
            ],
        )

        block = ma._build_indices_block(overview)
        prompt = ma._build_review_prompt(overview, [])
        report = ma._generate_template_review(overview, [])

        assert "| 上证指数 | N/A | N/A | N/A |" in block
        assert "| 深证成指 | 0.00 | ⚪ +0.00% | 0 |" in block
        assert block.count("⚪") == 1
        assert "- 上证指数: N/A (N/A)" in prompt
        assert "不要将缺失涨跌视为平盘" in prompt
        assert "今日A股市场整体呈现**数据不可用**态势" in report
        assert "- **上证指数**: N/A (N/A)" in report
        assert "- **深证成指**: 0.00 (-0.00%)" not in report

    def _assert_market_template_treats_authoritative_zero_as_flat(self):
        from src.market_analyzer import MarketOverview, MarketIndex

        ma = self._make_market_analyzer_with_mock_generate_text()
        overview = MarketOverview(
            date="2026-07-16",
            indices=[
                MarketIndex(
                    code="000001",
                    name="上证指数",
                    current=3200.0,
                    change=0.0,
                    change_pct=0.0,
                )
            ],
        )

        report = ma._generate_template_review(overview, [])

        assert "今日A股市场整体呈现**平盘**态势" in report
        assert "数据不可用" not in report

    def test_no_private_attribute_access_in_market_analyzer_source(self):
        """Static guard: market_analyzer.py must not access private analyzer attrs."""
        import ast
        import pathlib

        src = pathlib.Path("src/market_analyzer.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        forbidden = {
            "_model", "_router", "_use_openai", "_use_anthropic",  # historical
            "_call_litellm",      # use generate_text() instead
            "_litellm_available", # use is_available() instead
        }

        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                if node.attr in forbidden:
                    violations.append(node.attr)

        assert violations == [], (
            f"market_analyzer.py still accesses private Analyzer attributes: {violations}"
        )
