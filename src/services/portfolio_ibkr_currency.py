# -*- coding: utf-8 -*-
"""Currency classification owned by IBKR ingestion boundaries."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class IbkrCurrencyStatus(str, Enum):
    VALID = "valid"
    MISSING = "missing"
    MALFORMED = "malformed"
    UNKNOWN = "unknown"
    OPERATIONALLY_UNSUPPORTED = "operationally_unsupported"


@dataclass(frozen=True)
class IbkrCurrencyClassification:
    status: IbkrCurrencyStatus
    code: Optional[str] = None


# Active ISO 4217 alphabetic codes. Reserved testing/no-currency codes are
# intentionally excluded because they cannot identify a broker accounting unit.
_ISO_4217_CODES = frozenset(
    """
    AED AFN ALL AMD AOA ARS AUD AWG AZN BAM BBD BDT BGN BHD BIF BMD BND BOB
    BOV BRL BSD BTN BWP BYN BZD CAD CDF CHE CHF CHW CLF CLP CNY COP COU CRC
    CUC CUP CVE CZK DJF DKK DOP DZD EGP ERN ETB EUR FJD FKP GBP GEL GHS GIP
    GMD GNF GTQ GYD HKD HNL HTG HUF IDR ILS INR IQD IRR ISK JMD JOD JPY KES
    KGS KHR KMF KPW KRW KWD KYD KZT LAK LBP LKR LRD LSL LYD MAD MDL MGA MKD
    MMK MNT MOP MRU MUR MVR MWK MXN MXV MYR MZN NAD NGN NIO NOK NPR NZD OMR
    PAB PEN PGK PHP PKR PLN PYG QAR RON RSD RUB RWF SAR SBD SCR SDG SEK SGD
    SHP SLE SLL SOS SRD SSP STN SVC SYP SZL THB TJS TMT TND TOP TRY TTD TWD
    TZS UAH UGX USD USN UYI UYU UYW UZS VED VES VND VUV WST XAF XAG XAU XBA
    XBB XBC XBD XCD XDR XOF XPD XPF XPT XSU XUA YER ZAR ZMW ZWG
    """.split()
)


def classify_ibkr_currency(
    value: Any,
    *,
    operationally_supported: Optional[bool] = None,
) -> IbkrCurrencyClassification:
    """Classify broker-reported currency without inferring or truncating it."""
    if value is None:
        return IbkrCurrencyClassification(IbkrCurrencyStatus.MISSING)
    if not isinstance(value, str):
        return IbkrCurrencyClassification(IbkrCurrencyStatus.MALFORMED)

    text = value.strip()
    if not text:
        return IbkrCurrencyClassification(IbkrCurrencyStatus.MISSING)
    if re.fullmatch(r"[A-Za-z]{3}", text) is None:
        return IbkrCurrencyClassification(IbkrCurrencyStatus.MALFORMED)

    code = text.upper()
    if code not in _ISO_4217_CODES:
        return IbkrCurrencyClassification(IbkrCurrencyStatus.UNKNOWN)
    if operationally_supported is False:
        return IbkrCurrencyClassification(
            IbkrCurrencyStatus.OPERATIONALLY_UNSUPPORTED,
            code=code,
        )
    return IbkrCurrencyClassification(IbkrCurrencyStatus.VALID, code=code)
