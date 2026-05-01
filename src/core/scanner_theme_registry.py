# -*- coding: utf-8 -*-
"""Curated and runtime-generated scanner theme universes."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import re
from typing import Dict, List, Optional, Sequence, Tuple


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
    criteria_prompt: Optional[str] = None
    generated_at: Optional[str] = None
    updated_at: Optional[str] = None
    refresh_policy: Optional[str] = None
    ai_metadata: Optional[Dict[str, object]] = None

    def to_dict(self) -> Dict[str, object]:
        payload = asdict(self)
        payload["symbols"] = list(self.symbols)
        payload["aliases"] = list(self.aliases)
        payload["tags"] = list(self.tags)
        payload["ai_metadata"] = dict(self.ai_metadata or {})
        return payload


@dataclass(frozen=True)
class ScannerThemeSuggestion:
    symbol: str
    reason: str
    confidence: float = 0.7
    evidence: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, object]:
        payload = asdict(self)
        payload["evidence"] = list(self.evidence)
        return payload


# Product note: these are static seed lists. Future user-owned or AI-generated
# theme discovery belongs in a separate custom theme builder, not endless
# hardcoded additions to this registry.
SCANNER_THEMES: Tuple[ScannerTheme, ...] = (
    ScannerTheme(
        id="crypto_miners",
        label_zh="加密矿企",
        label_en="Crypto miners",
        market="us",
        description="US-listed crypto mining and adjacent mining infrastructure seed list; not an authoritative industry classification.",
        symbols=("MARA", "RIOT", "CLSK", "IREN", "CIFR", "HUT", "BTDR", "WULF", "CORZ", "BITF", "HIVE"),
        aliases=("bitcoin miners", "crypto mining"),
        tags=("crypto", "miners", "us"),
    ),
    ScannerTheme(
        id="memory_storage",
        label_zh="存储/硬盘",
        label_en="Memory / storage",
        market="us",
        description="US-listed memory, storage and hard-disk related seed list; not an authoritative industry classification.",
        symbols=("MU", "WDC", "STX", "NTAP", "PSTG"),
        aliases=("memory", "storage", "hard disk"),
        tags=("memory", "storage", "us"),
    ),
    ScannerTheme(
        id="optical_networking",
        label_zh="光通信/网络",
        label_en="Optical networking",
        market="us",
        description="US-listed optical networking, components and datacenter networking seed list.",
        symbols=("CIEN", "LITE", "COHR", "AAOI", "FN", "ANET", "GLW"),
        aliases=("optical networking", "cpo", "datacenter networking"),
        tags=("optical", "networking", "us"),
    ),
    ScannerTheme(
        id="ai_semiconductors",
        label_zh="AI 半导体",
        label_en="AI semiconductors",
        market="us",
        description="US-listed AI semiconductor and semiconductor capital-equipment seed list.",
        symbols=("NVDA", "AMD", "AVGO", "MRVL", "ARM", "TSM", "ASML", "AMAT", "LRCX", "KLAC"),
        aliases=("ai chips", "semiconductors"),
        tags=("ai", "semiconductors", "us"),
    ),
    ScannerTheme(
        id="liquid_cooling_power",
        label_zh="液冷/电力",
        label_en="Liquid cooling / power",
        market="us",
        description="US-listed datacenter cooling, power and thermal infrastructure seed list.",
        symbols=("VRT", "ETN", "PWR", "MOD", "TT", "JCI", "CARR", "SMCI"),
        aliases=("liquid cooling", "datacenter power", "thermal infrastructure"),
        tags=("cooling", "power", "us"),
    ),
    ScannerTheme(
        id="data_center_infra",
        label_zh="数据中心基础设施",
        label_en="Data center infrastructure",
        market="us",
        description="US-listed datacenter infrastructure, power, REIT, server and networking seed list.",
        symbols=("VRT", "ETN", "PWR", "DLR", "EQIX", "SMCI", "ANET", "NTAP"),
        aliases=("data center", "datacenter infrastructure"),
        tags=("datacenter", "infrastructure", "us"),
    ),
    ScannerTheme(
        id="robotics_automation",
        label_zh="机器人/自动化",
        label_en="Robotics / automation",
        market="us",
        description="US-listed robotics, automation and industrial automation seed list.",
        symbols=("ISRG", "TER", "SYM", "PATH", "ROK", "ABBNY", "HON"),
        aliases=("robotics", "automation"),
        tags=("robotics", "automation", "us"),
    ),
    ScannerTheme(
        id="cybersecurity",
        label_zh="网络安全",
        label_en="Cybersecurity",
        market="us",
        description="US-listed cybersecurity software and cloud security seed list.",
        symbols=("CRWD", "PANW", "ZS", "FTNT", "NET", "OKTA", "S"),
        aliases=("security software", "cloud security"),
        tags=("cybersecurity", "software", "us"),
    ),
    ScannerTheme(
        id="quantum",
        label_zh="量子计算",
        label_en="Quantum",
        market="us",
        description="US-listed quantum computing and related seed list.",
        symbols=("IONQ", "RGTI", "QBTS", "QUBT", "ARQQ"),
        aliases=("quantum computing",),
        tags=("quantum", "us"),
    ),
    ScannerTheme(
        id="defense_aerospace",
        label_zh="国防/航空航天",
        label_en="Defense / aerospace",
        market="us",
        description="US-listed defense, aerospace and defense-software seed list.",
        symbols=("LMT", "RTX", "NOC", "GD", "BA", "KTOS", "PLTR"),
        aliases=("defense", "aerospace"),
        tags=("defense", "aerospace", "us"),
    ),
    ScannerTheme(
        id="nuclear_uranium",
        label_zh="核能/铀",
        label_en="Nuclear / uranium",
        market="us",
        description="US-listed uranium, nuclear energy and advanced reactor seed list.",
        symbols=("CCJ", "UEC", "LEU", "SMR", "OKLO", "BWXT"),
        aliases=("nuclear", "uranium"),
        tags=("nuclear", "uranium", "us"),
    ),
    ScannerTheme(
        id="weight_loss_glp1",
        label_zh="减重/GLP-1",
        label_en="Weight loss / GLP-1",
        market="us",
        description="US-listed and US-traded GLP-1 obesity drug seed list.",
        symbols=("LLY", "NVO", "VKTX", "AMGN", "PFE"),
        aliases=("glp-1", "weight loss", "obesity drugs"),
        tags=("healthcare", "glp1", "us"),
    ),
    ScannerTheme(
        id="cloud_ai_software",
        label_zh="云/AI 软件",
        label_en="Cloud AI software",
        market="us",
        description="US-listed cloud, AI platform and data software seed list.",
        symbols=("MSFT", "GOOGL", "AMZN", "META", "NOW", "SNOW", "DDOG", "MDB", "PLTR"),
        aliases=("cloud ai", "data software", "ai software"),
        tags=("cloud", "ai", "software", "us"),
    ),
)

_CN_HK_PLACEHOLDER_THEMES: Tuple[Tuple[str, str, str, str, Tuple[str, ...], Tuple[str, ...]], ...] = (
    ("optical_module_cpo", "光模块 CPO", "Optical module / CPO", "optical module / CPO", ("cpo", "optical modules"), ("optical", "cpo")),
    ("liquid_cooling", "液冷", "Liquid cooling", "liquid cooling", ("liquid cooling",), ("cooling",)),
    ("compute_leasing", "算力租赁", "Compute leasing", "compute leasing", ("compute leasing",), ("compute",)),
    ("memory_storage", "存储", "Memory / storage", "memory / storage", ("memory", "storage"), ("memory", "storage")),
    ("semiconductor_equipment", "半导体设备", "Semiconductor equipment", "semiconductor equipment", ("semiconductor equipment",), ("semiconductor", "equipment")),
    ("robotics", "机器人", "Robotics", "robotics", ("robotics",), ("robotics",)),
    ("ai_chip", "AI 芯片", "AI chip", "AI chip", ("ai chip",), ("ai", "chip")),
    ("data_center_power", "数据中心电源", "Data center power", "data center power", ("data center power",), ("datacenter", "power")),
    ("low_altitude_economy", "低空经济", "Low-altitude economy", "low-altitude economy", ("low altitude economy",), ("low-altitude",)),
    ("humanoid_robot", "人形机器人", "Humanoid robot", "humanoid robot", ("humanoid robot",), ("humanoid", "robotics")),
    ("solid_state_battery", "固态电池", "Solid-state battery", "solid-state battery", ("solid state battery",), ("battery",)),
    ("satellite_internet", "卫星互联网", "Satellite internet", "satellite internet", ("satellite internet",), ("satellite",)),
)

SCANNER_THEMES = SCANNER_THEMES + tuple(
    ScannerTheme(
        id=f"{theme_id}_{market}",
        label_zh=label_zh,
        label_en=label_en,
        market=market,
        description=(
            f"{market.upper()} {description_fragment} theme placeholder. Constituents are not configured; "
            "this is a seed slot that requires manual verification before it can run."
        ),
        symbols=(),
        aliases=aliases,
        tags=(*tags, market),
        source="manual_placeholder",
        requires_manual_maintenance=True,
    )
    for market in ("cn", "hk")
    for theme_id, label_zh, label_en, description_fragment, aliases, tags in _CN_HK_PLACEHOLDER_THEMES
)

_THEMES_BY_ID = {theme.id: theme for theme in SCANNER_THEMES}
_CUSTOM_THEMES_BY_ID: Dict[str, ScannerTheme] = {}
_THEME_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_]{2,63}$")

_AI_THEME_CATALOG: Dict[str, Tuple[ScannerThemeSuggestion, ...]] = {
    "white_house": (
        ScannerThemeSuggestion("PLTR", "Federal analytics and defense contracts are central to the policy-linked thesis.", 0.86, ("federal contracts", "defense analytics")),
        ScannerThemeSuggestion("LMT", "Large defense prime with direct sensitivity to White House and Pentagon budget priorities.", 0.82, ("defense budget", "federal procurement")),
        ScannerThemeSuggestion("RTX", "Defense and aerospace exposure tied to federal procurement and geopolitical policy.", 0.78, ("defense procurement", "aerospace policy")),
        ScannerThemeSuggestion("NOC", "Defense prime often affected by national security spending and administration priorities.", 0.76, ("national security", "federal procurement")),
        ScannerThemeSuggestion("GD", "Defense contractor linked to federal budget cycles and military procurement.", 0.74, ("federal budget", "military procurement")),
        ScannerThemeSuggestion("BA", "Aerospace and defense exposure with policy and government-contract sensitivity.", 0.68, ("aerospace", "government contracts")),
    ),
    "ai_semiconductor": (
        ScannerThemeSuggestion("NVDA", "Leading AI accelerator supplier with direct exposure to AI infrastructure demand.", 0.92, ("AI accelerators", "datacenter GPUs")),
        ScannerThemeSuggestion("AMD", "AI accelerator and CPU supplier competing in datacenter AI infrastructure.", 0.84, ("AI accelerators", "datacenter compute")),
        ScannerThemeSuggestion("TSM", "Advanced foundry exposure to AI chip demand across fabless customers.", 0.82, ("advanced foundry", "AI chip supply chain")),
        ScannerThemeSuggestion("AVGO", "Custom silicon, networking, and accelerator-adjacent AI infrastructure exposure.", 0.78, ("custom silicon", "AI networking")),
        ScannerThemeSuggestion("ASML", "Lithography equipment bottleneck for advanced AI semiconductor manufacturing.", 0.76, ("EUV lithography", "semicap equipment")),
    ),
    "green_energy": (
        ScannerThemeSuggestion("ENPH", "Solar inverter and home energy storage exposure.", 0.82, ("solar", "distributed energy")),
        ScannerThemeSuggestion("RUN", "Residential solar installation and financing exposure.", 0.76, ("residential solar", "energy transition")),
        ScannerThemeSuggestion("FSLR", "US solar module manufacturer tied to domestic clean-energy policy.", 0.78, ("solar modules", "clean-energy policy")),
        ScannerThemeSuggestion("JKS", "Global solar module manufacturer with clean-energy supply chain exposure.", 0.7, ("solar modules", "renewables")),
        ScannerThemeSuggestion("NEE", "Utility-scale renewables and clean-power infrastructure exposure.", 0.68, ("renewable power", "utility-scale clean energy")),
    ),
    "robotics": (
        ScannerThemeSuggestion("ISRG", "Surgical robotics leader with direct automation exposure.", 0.86, ("surgical robotics", "medical automation")),
        ScannerThemeSuggestion("TER", "Industrial automation and robotics testing exposure.", 0.76, ("automation", "robotics testing")),
        ScannerThemeSuggestion("ABBNY", "Industrial robotics and automation exposure through ABB ADR.", 0.74, ("industrial robotics", "automation")),
        ScannerThemeSuggestion("ROK", "Factory automation and industrial control exposure.", 0.72, ("factory automation", "industrial controls")),
        ScannerThemeSuggestion("SYM", "Warehouse automation and robotics exposure.", 0.7, ("warehouse automation", "robotics")),
    ),
    "ai_chip_cn_hk": (
        ScannerThemeSuggestion("0981", "SMIC is a core Greater China semiconductor manufacturing proxy.", 0.82, ("foundry", "AI chip supply chain")),
        ScannerThemeSuggestion("2330", "TSMC is a key advanced foundry proxy for AI chip manufacturing.", 0.86, ("advanced foundry", "AI chips")),
    ),
}

_PROMPT_KEYWORDS: Tuple[Tuple[Tuple[str, ...], str], ...] = (
    (("white house", "government", "federal", "policy", "pentagon", "defense"), "white_house"),
    (("ai semiconductor", "ai chip", "semiconductor", "gpu", "accelerator"), "ai_semiconductor"),
    (("green energy", "clean energy", "solar", "renewable"), "green_energy"),
    (("robot", "robotics", "automation", "humanoid"), "robotics"),
    (("smic", "tsmc", "ai chip", "ai chips"), "ai_chip_cn_hk"),
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_symbol_for_theme(symbol: str, *, market: str) -> Optional[str]:
    normalized = str(symbol or "").strip().upper()
    if not normalized:
        return None
    if market == "us":
        return normalized if re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", normalized) else None
    if market in {"cn", "hk"}:
        digits = re.sub(r"\D", "", normalized)
        if market == "hk":
            return digits.zfill(5) if 1 <= len(digits) <= 5 else None
        return digits if len(digits) == 6 else None
    return None


def _select_catalog_key(prompt: str, *, market: str) -> str:
    normalized = prompt.lower()
    for keywords, catalog_key in _PROMPT_KEYWORDS:
        if any(keyword in normalized for keyword in keywords):
            if catalog_key == "ai_chip_cn_hk" and market not in {"cn", "hk"}:
                continue
            return catalog_key
    return "ai_semiconductor" if market == "us" else "ai_chip_cn_hk"


def _suggest_theme_symbols(
    *,
    market: str,
    prompt: str,
    manual_symbols: Sequence[str] = (),
) -> Tuple[ScannerThemeSuggestion, ...]:
    catalog_key = _select_catalog_key(prompt, market=market)
    suggestions: List[ScannerThemeSuggestion] = []
    seen = set()
    for raw_symbol in manual_symbols:
        symbol = _normalize_symbol_for_theme(raw_symbol, market=market)
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        suggestions.append(
            ScannerThemeSuggestion(
                symbol=symbol,
                reason="Manually added by the user during custom theme creation.",
                confidence=1.0,
                evidence=("manual adjustment",),
            )
        )
    for suggestion in _AI_THEME_CATALOG.get(catalog_key, ()):
        symbol = _normalize_symbol_for_theme(suggestion.symbol, market=market)
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        suggestions.append(suggestion if symbol == suggestion.symbol else ScannerThemeSuggestion(symbol, suggestion.reason, suggestion.confidence, suggestion.evidence))
    return tuple(suggestions)


def create_ai_scanner_theme(
    *,
    theme_id: str,
    label: str,
    market: str,
    prompt: str,
    manual_symbols: Sequence[str] = (),
) -> Tuple[ScannerTheme, Tuple[ScannerThemeSuggestion, ...]]:
    normalized_id = (theme_id or "").strip().lower()
    normalized_market = (market or "").strip().lower()
    normalized_label = (label or "").strip()
    normalized_prompt = (prompt or "").strip()

    if not _THEME_ID_PATTERN.fullmatch(normalized_id):
        raise ValueError("scanner theme id must use 3-64 lowercase letters, numbers, or underscores")
    if normalized_id in _THEMES_BY_ID:
        raise ValueError(f"scanner theme id already exists: {normalized_id}")
    if normalized_market not in {"cn", "us", "hk"}:
        raise ValueError(f"unsupported scanner theme market: {market}")
    if len(normalized_label) < 2:
        raise ValueError("scanner theme label is required")
    if len(normalized_prompt) < 12:
        raise ValueError("scanner theme prompt is too short")

    suggestions = _suggest_theme_symbols(
        market=normalized_market,
        prompt=normalized_prompt,
        manual_symbols=manual_symbols,
    )
    if not suggestions:
        raise ValueError("AI theme generation returned no valid symbols for this market")

    now = _now_iso()
    symbols = tuple(suggestion.symbol for suggestion in suggestions)
    theme = ScannerTheme(
        id=normalized_id,
        label_zh=normalized_label,
        label_en=normalized_label,
        market=normalized_market,
        description=f"AI-generated custom scanner theme from user criteria: {normalized_prompt}",
        symbols=symbols,
        aliases=(normalized_label, normalized_prompt[:80]),
        tags=("custom", "ai-generated", normalized_market),
        source="ai_generated",
        version=now[:10],
        is_seed_list=False,
        requires_manual_maintenance=True,
        criteria_prompt=normalized_prompt,
        generated_at=now,
        updated_at=now,
        refresh_policy="on_demand",
        ai_metadata={
            "status": "generated",
            "method": "prompt_catalog_with_manual_adjustments",
            "catalog_key": _select_catalog_key(normalized_prompt, market=normalized_market),
            "message": "Generated from prompt criteria and available scanner theme knowledge; review before trading.",
        },
    )
    _CUSTOM_THEMES_BY_ID[normalized_id] = theme
    return theme, suggestions


def list_scanner_themes(*, market: Optional[str] = None) -> List[ScannerTheme]:
    normalized_market = (market or "").strip().lower()
    return [
        theme
        for theme in (*SCANNER_THEMES, *_CUSTOM_THEMES_BY_ID.values())
        if not normalized_market or theme.market == normalized_market
    ]


def get_scanner_theme(theme_id: str) -> Optional[ScannerTheme]:
    normalized_id = (theme_id or "").strip().lower()
    return _CUSTOM_THEMES_BY_ID.get(normalized_id) or _THEMES_BY_ID.get(normalized_id)
