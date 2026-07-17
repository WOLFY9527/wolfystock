"""Narrow normalized acquisition ports for provider-backed data."""

from src.providers.ports.history import HistoryBar, HistoryData, HistoryPort, HistoryRequest
from src.providers.ports.macro import MacroData, MacroPort, MacroRequest
from src.providers.ports.normalization import provider_error_result_from_exception
from src.providers.ports.quote import QuoteData, QuotePort, QuoteRequest

__all__ = [
    "HistoryBar",
    "HistoryData",
    "HistoryPort",
    "HistoryRequest",
    "MacroData",
    "MacroPort",
    "MacroRequest",
    "QuoteData",
    "QuotePort",
    "QuoteRequest",
    "provider_error_result_from_exception",
]
