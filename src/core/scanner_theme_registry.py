# -*- coding: utf-8 -*-
"""Curated scanner theme universes."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ScannerTheme:
    id: str
    label_zh: str
    label_en: str
    market: str
    description: str
    symbols: Tuple[str, ...]
    aliases: Tuple[str, ...] = ()
    tags: Tuple[str, ...] = ()
    source: str = "curated_seed"
    version: str = "2026-05-01"
    is_seed_list: bool = True
    requires_manual_maintenance: bool = False

    def to_dict(self) -> Dict[str, object]:
        payload = asdict(self)
        payload["symbols"] = list(self.symbols)
        payload["aliases"] = list(self.aliases)
        payload["tags"] = list(self.tags)
        return payload


SCANNER_THEMES: Tuple[ScannerTheme, ...] = (
    ScannerTheme(
        id="crypto_miners",
        label_zh="加密矿企",
        label_en="Crypto miners",
        market="us",
        description="US-listed crypto mining and adjacent mining infrastructure seed list.",
        symbols=("MARA", "RIOT", "CLSK", "IREN", "HUT", "BITF", "WULF", "CIFR"),
        aliases=("bitcoin miners", "crypto mining"),
        tags=("crypto", "miners", "us"),
    ),
    ScannerTheme(
        id="memory_storage_us",
        label_zh="存储/硬盘",
        label_en="Memory / storage",
        market="us",
        description="US-listed memory, storage and hard-disk related seed list.",
        symbols=("MU", "WDC", "STX"),
        aliases=("memory", "storage", "hard disk"),
        tags=("memory", "storage", "us"),
    ),
    ScannerTheme(
        id="ai_semiconductors_us",
        label_zh="AI 半导体",
        label_en="AI semiconductors",
        market="us",
        description="US-listed AI semiconductor and semiconductor ETF seed list.",
        symbols=("NVDA", "AMD", "AVGO", "MRVL", "ARM", "SMH"),
        aliases=("ai chips", "semiconductors"),
        tags=("ai", "semiconductors", "us"),
    ),
    ScannerTheme(
        id="optical_modules_cpo_cn",
        label_zh="光模块/CPO",
        label_en="Optical modules / CPO",
        market="cn",
        description="A-share optical module / CPO theme placeholder. Constituents are not configured and require manual verification.",
        symbols=(),
        aliases=("cpo", "optical modules"),
        tags=("optical", "cpo", "cn"),
        source="manual_placeholder",
        requires_manual_maintenance=True,
    ),
    ScannerTheme(
        id="liquid_cooling_cn",
        label_zh="液冷",
        label_en="Liquid cooling",
        market="cn",
        description="A-share liquid cooling theme placeholder. Constituents are not configured and require manual verification.",
        symbols=(),
        aliases=("liquid cooling",),
        tags=("cooling", "cn"),
        source="manual_placeholder",
        requires_manual_maintenance=True,
    ),
    ScannerTheme(
        id="compute_leasing_cn",
        label_zh="算力租赁",
        label_en="Compute leasing",
        market="cn",
        description="A-share compute leasing theme placeholder. Constituents are not configured and require manual verification.",
        symbols=(),
        aliases=("compute leasing",),
        tags=("compute", "cn"),
        source="manual_placeholder",
        requires_manual_maintenance=True,
    ),
    ScannerTheme(
        id="memory_storage_cn",
        label_zh="存储",
        label_en="Memory / storage",
        market="cn",
        description="A-share memory / storage theme placeholder. Constituents are not configured and require manual verification.",
        symbols=(),
        aliases=("memory", "storage"),
        tags=("memory", "storage", "cn"),
        source="manual_placeholder",
        requires_manual_maintenance=True,
    ),
    ScannerTheme(
        id="semiconductor_equipment_cn",
        label_zh="半导体设备",
        label_en="Semiconductor equipment",
        market="cn",
        description="A-share semiconductor equipment theme placeholder. Constituents are not configured and require manual verification.",
        symbols=(),
        aliases=("semiconductor equipment",),
        tags=("semiconductor", "equipment", "cn"),
        source="manual_placeholder",
        requires_manual_maintenance=True,
    ),
    ScannerTheme(
        id="robotics_cn",
        label_zh="机器人",
        label_en="Robotics",
        market="cn",
        description="A-share robotics theme placeholder. Constituents are not configured and require manual verification.",
        symbols=(),
        aliases=("robotics",),
        tags=("robotics", "cn"),
        source="manual_placeholder",
        requires_manual_maintenance=True,
    ),
)

_THEMES_BY_ID = {theme.id: theme for theme in SCANNER_THEMES}


def list_scanner_themes(*, market: Optional[str] = None) -> List[ScannerTheme]:
    normalized_market = (market or "").strip().lower()
    return [
        theme
        for theme in SCANNER_THEMES
        if not normalized_market or theme.market == normalized_market
    ]


def get_scanner_theme(theme_id: str) -> Optional[ScannerTheme]:
    return _THEMES_BY_ID.get((theme_id or "").strip().lower())
