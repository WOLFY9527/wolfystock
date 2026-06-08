# -*- coding: utf-8 -*-
"""Unit tests for report language helpers."""

import unittest

from src.report_language import (
    get_bias_status_emoji,
    get_localized_stock_name,
    get_report_labels,
    get_sentiment_label,
    get_signal_level,
    localize_bias_status,
    localize_operation_advice,
)


class ReportLanguageTestCase(unittest.TestCase):
    def test_get_signal_level_handles_compound_sell_advice(self) -> None:
        signal_text, emoji, signal_tag = get_signal_level("卖出/观望", 60, "zh")

        self.assertEqual(signal_text, "风险收缩")
        self.assertEqual(emoji, "🔴")
        self.assertEqual(signal_tag, "sell")

    def test_get_signal_level_handles_compound_buy_advice_in_english(self) -> None:
        signal_text, emoji, signal_tag = get_signal_level("Buy / Watch", 40, "en")

        self.assertEqual(signal_text, "Positive observation")
        self.assertEqual(emoji, "🟢")
        self.assertEqual(signal_tag, "buy")

    def test_public_report_labels_use_observation_language(self) -> None:
        forbidden = (
            "买入",
            "卖出",
            "加仓",
            "减仓",
            "建仓",
            "仓位建议",
            "止损",
            "止盈",
            "目标价",
            "目标位",
            "作战计划",
            "理想买入点",
            "空仓者建议",
            "持仓者建议",
            "Buy",
            "Sell",
            "Hold",
            "Entry",
            "Stop Loss",
            "Take Profit",
            "Target",
            "Position Size",
            "Battle Plan",
        )
        public_values = [
            localize_operation_advice("buy", "zh"),
            localize_operation_advice("sell", "zh"),
            localize_operation_advice("buy", "en"),
            localize_operation_advice("sell", "en"),
            *get_report_labels("zh").values(),
            *get_report_labels("en").values(),
        ]
        serialized = "\n".join(str(value) for value in public_values)

        for term in forbidden:
            self.assertNotIn(term, serialized, term)
        self.assertIn("研究观察仪表盘", serialized)
        self.assertIn("Research Observation Dashboard", serialized)
        self.assertIn("仅供研究观察，不构成投资建议", serialized)

    def test_get_localized_stock_name_replaces_placeholder_for_english(self) -> None:
        self.assertEqual(
            get_localized_stock_name("股票AAPL", "AAPL", "en"),
            "Unnamed Stock",
        )

    def test_get_sentiment_label_preserves_higher_band_thresholds(self) -> None:
        self.assertEqual(get_sentiment_label(80, "en"), "Very Bullish")
        self.assertEqual(get_sentiment_label(60, "en"), "Bullish")
        self.assertEqual(get_sentiment_label(40, "zh"), "中性")
        self.assertEqual(get_sentiment_label(20, "zh"), "悲观")

    def test_bias_status_helpers_support_english_values(self) -> None:
        self.assertEqual(localize_bias_status("Safe", "en"), "Safe")
        self.assertEqual(localize_bias_status("警戒", "en"), "Caution")
        self.assertEqual(get_bias_status_emoji("Safe"), "✅")
        self.assertEqual(get_bias_status_emoji("Caution"), "⚠️")


if __name__ == "__main__":
    unittest.main()
