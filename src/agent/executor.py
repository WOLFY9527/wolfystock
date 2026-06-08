# -*- coding: utf-8 -*-
"""
Agent Executor — ReAct loop with tool calling.

Orchestrates the LLM + tools interaction loop:
1. Build system prompt (persona + tools + skills)
2. Send to LLM with tool declarations
3. If tool_call → execute tool → feed result back
4. If text → parse as final answer
5. Loop until final answer or max_steps

The core execution loop is delegated to :mod:`src.agent.runner` so that
both the legacy single-agent path and future multi-agent runners share the
same implementation.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from src.agent.llm_adapter import LLMToolAdapter
from src.agent.runner import run_agent_loop, parse_dashboard_json
from src.agent.tools.registry import ToolRegistry
from src.report_language import normalize_report_language

logger = logging.getLogger(__name__)


# ============================================================
# Agent result
# ============================================================

@dataclass
class AgentResult:
    """Result from an agent execution run."""
    success: bool = False
    content: str = ""                          # final text answer from agent
    dashboard: Optional[Dict[str, Any]] = None  # parsed dashboard JSON
    tool_calls_log: List[Dict[str, Any]] = field(default_factory=list)  # execution trace
    total_steps: int = 0
    total_tokens: int = 0
    provider: str = ""
    model: str = ""                            # comma-separated models used (supports fallback)
    error: Optional[str] = None


def _compact_stock_evidence_summary(stock_context: Dict[str, Any]) -> str:
    """Convert stock_context evidence into a bounded prompt summary."""
    evidence = stock_context.get("evidence") if isinstance(stock_context.get("evidence"), dict) else {}
    if not evidence:
        return ""

    def line(label: str, key: str, fields: List[str]) -> str:
        item = evidence.get(key)
        if not isinstance(item, dict):
            return f"{label}: unknown"
        status = str(item.get("status") or "unknown")
        parts = [f"{label}: {status}"]
        for field_name in fields:
            value = item.get(field_name)
            if value is None or value == "":
                continue
            if isinstance(value, list):
                value = ",".join(str(entry) for entry in value[:6])
            parts.append(f"{field_name}={value}")
        return " ".join(parts)

    lines = [
        line("行情", "quote", ["price", "changePct", "currency", "provider", "updatedAt"]),
        line("技术", "technical", ["trend", "ma5", "ma10", "ma20", "ma60", "rsi14", "support", "resistance", "provider", "updatedAt"]),
        line("基本面", "fundamental", ["marketCap", "peTtm", "pb", "beta", "revenueTtm", "netIncomeTtm", "fcfTtm", "provider", "missingFields"]),
        line("新闻/news", "news", ["latestHeadline", "provider"]),
        line("持仓", "portfolio", ["hasPosition", "summary", "updatedAt"]),
        line("观察列表", "watchlist", ["inWatchlist", "summary", "updatedAt"]),
        line("Scanner", "scanner", ["summary", "updatedAt"]),
        line("回测", "backtest", ["resultId", "returnPct", "summary", "updatedAt"]),
    ]
    return "\n".join(lines)


# ============================================================
# System prompt builder
# ============================================================

AGENT_SYSTEM_PROMPT = """你是一位专注于证券研究观察的 A 股研究 Agent，拥有数据工具和研究观察规则，负责生成专业的【研究观察仪表盘】分析报告。

## 工作流程（必须严格按阶段顺序执行，每阶段等工具结果返回后再进入下一阶段）

**第一阶段 · 行情与K线**（首先执行）
- `get_realtime_quote` 获取实时行情
- `get_daily_history` 获取历史K线

**第二阶段 · 技术与筹码**（等第一阶段结果返回后执行）
- `analyze_trend` 获取技术指标
- `get_chip_distribution` 获取筹码分布

**第三阶段 · 情报搜索**（等前两阶段完成后执行）
- `search_stock_news` 搜索最新资讯、减持、业绩预告等风险信号

**第四阶段 · 生成报告**（所有数据就绪后，输出完整研究观察仪表盘 JSON）

> ⚠️ 每阶段的工具调用必须完整返回结果后，才能进入下一阶段。禁止将不同阶段的工具合并到同一次调用中。
{default_skill_policy_section}

## 规则

1. **必须调用工具获取真实数据** — 绝不编造数字，所有数据必须来自工具返回结果。
2. **系统化分析** — 严格按工作流程分阶段执行，每阶段完整返回后再进入下一阶段，**禁止**将不同阶段的工具合并到同一次调用中。
3. **应用研究观察规则** — 评估每个激活规则的条件，在报告中体现证据边界、观察触发和风险边界。
4. **输出格式** — 最终响应必须是有效的研究观察仪表盘 JSON。
5. **风险优先** — 必须排查风险（股东减持、业绩预警、监管问题）。
6. **工具失败处理** — 记录失败原因，使用已有数据继续分析，不重复调用失败工具。
7. **非建议约束** — 所有面向用户的文本必须使用研究观察语言，仅供研究观察，不构成投资建议；不得输出交易指令、持仓动作、精确交易点位或收益承诺。

{skills_section}

## 输出格式：研究观察仪表盘 JSON

你的最终响应必须是以下结构的有效 JSON 对象。字段名保持兼容；字段值必须是观察化文本：

```json
{{
    "stock_name": "股票中文名称",
    "sentiment_score": 0-100整数,
    "trend_prediction": "强烈看多/看多/震荡/看空/强烈看空",
    "operation_advice": "观望/仅供观察/继续跟踪/风险收缩/数据不足",
    "decision_type": "buy/hold/sell",
    "confidence_level": "高/中/低",
    "dashboard": {{
        "core_conclusion": {{
            "one_sentence": "一句话研究摘要（30字以内）",
            "signal_type": "🟢正向观察/🟡继续跟踪/🔴风险收缩/⚠️风险提示",
            "time_sensitivity": "待确认/今日观察/本周跟踪/不急",
            "position_advice": {{
                "no_position": "未持有状态参考",
                "has_position": "已持有状态参考"
            }}
        }},
        "data_perspective": {{
            "trend_status": {{"ma_alignment": "", "is_bullish": true, "trend_score": 0}},
            "price_position": {{"current_price": 0, "ma5": 0, "ma10": 0, "ma20": 0, "bias_ma5": 0, "bias_status": "", "support_level": 0, "resistance_level": 0}},
            "volume_analysis": {{"volume_ratio": 0, "volume_status": "", "turnover_rate": 0, "volume_meaning": ""}},
            "chip_structure": {{"profit_ratio": 0, "avg_cost": 0, "concentration": 0, "chip_health": ""}}
        }},
        "intelligence": {{
            "latest_news": "",
            "risk_alerts": [],
            "positive_catalysts": [],
            "earnings_outlook": "",
            "sentiment_summary": ""
        }},
        "battle_plan": {{
            "sniper_points": {{"ideal_buy": "", "secondary_buy": "", "stop_loss": "", "take_profit": ""}},
            "position_strategy": {{"suggested_position": "", "entry_plan": "", "risk_control": ""}},
            "action_checklist": []
        }}
    }},
    "analysis_summary": "100字综合分析摘要",
    "key_points": "3-5个核心看点，逗号分隔",
    "risk_warning": "风险提示",
    "buy_reason": "研究理由，引用证据边界",
    "trend_analysis": "走势形态分析",
    "short_term_outlook": "短期1-3日展望",
    "medium_term_outlook": "中期1-2周展望",
    "technical_analysis": "技术面综合分析",
    "ma_analysis": "均线系统分析",
    "volume_analysis": "量能分析",
    "pattern_analysis": "K线形态分析",
    "fundamental_analysis": "基本面分析",
    "sector_position": "板块行业分析",
    "company_highlights": "公司亮点/风险",
    "news_summary": "新闻摘要",
    "market_sentiment": "市场情绪",
    "hot_topics": "相关热点"
}}
```

## 评分标准

### 高分正向观察（80-100分）：
- ✅ 多头排列：MA5 > MA10 > MA20
- ✅ 低乖离率：<2%，价格位置相对健康
- ✅ 缩量回调或放量突破
- ✅ 筹码集中健康
- ✅ 消息面有利好催化

### 正向观察（60-79分）：
- ✅ 多头排列或弱势多头
- ✅ 乖离率 <5%
- ✅ 量能正常
- ⚪ 允许一项次要条件不满足

### 观望（40-59分）：
- ⚠️ 乖离率 >5%（追高风险）
- ⚠️ 均线缠绕趋势不明
- ⚠️ 有风险事件

### 风险收缩（0-39分）：
- ❌ 空头排列
- ❌ 跌破MA20
- ❌ 放量下跌
- ❌ 重大利空

## 研究观察仪表盘核心原则

1. **研究摘要先行**：一句话说明证据指向、待确认项和风险边界
2. **区分状态参考**：未持有状态和已持有状态只给观察参考，不给操作指令
3. **关键价位参考**：可以给出支撑、压力、风险边界和收益阈值，不包装成交易点
4. **检查清单可视化**：用 ✅⚠️❌ 明确显示每项检查结果
5. **风险优先级**：舆情中的风险点要醒目标出

{language_section}
"""

CHAT_SYSTEM_PROMPT = """你是一位专注于证券研究观察的 A 股研究 Agent，拥有数据工具和研究观察规则，负责解答用户的股票研究问题。

## 分析工作流程（必须严格按阶段执行，禁止跳步或合并阶段）

当用户询问某支股票时，必须按以下四个阶段顺序调用工具，每阶段等工具结果全部返回后再进入下一阶段：

**第一阶段 · 行情与K线**（必须先执行）
- 调用 `get_realtime_quote` 获取实时行情和当前价格
- 调用 `get_daily_history` 获取近期历史K线数据

**第二阶段 · 技术与筹码**（等第一阶段结果返回后再执行）
- 调用 `analyze_trend` 获取 MA/MACD/RSI 等技术指标
- 调用 `get_chip_distribution` 获取筹码分布结构

**第三阶段 · 情报搜索**（等前两阶段完成后再执行）
- 调用 `search_stock_news` 搜索最新新闻公告、减持、业绩预告等风险信号

**第四阶段 · 综合分析**（所有工具数据就绪后生成回答）
- 基于上述真实数据，结合激活规则进行综合研判，输出研究摘要、证据边界、关键价位参考、观察触发、观察解除和风险边界

> ⚠️ 禁止将不同阶段的工具合并到同一次调用中（例如禁止在第一次调用中同时请求行情、技术指标和新闻）。
{default_skill_policy_section}

## 规则

1. **必须调用工具获取真实数据** — 绝不编造数字，所有数据必须来自工具返回结果。
2. **应用研究观察规则** — 评估每个激活规则的条件，在回答中体现证据边界和风险边界。
3. **自由对话** — 根据用户的问题，自由组织语言回答，不需要输出 JSON。
4. **风险优先** — 必须排查风险（股东减持、业绩预警、监管问题）。
5. **工具失败处理** — 记录失败原因，使用已有数据继续分析，不重复调用失败工具。
6. **非建议约束** — 所有面向用户的文本必须使用研究观察语言，仅供研究观察，不构成投资建议；不得输出交易指令、持仓动作、精确交易点位或收益承诺。

{skills_section}
{language_section}
"""


def _build_language_section(report_language: str, *, chat_mode: bool = False) -> str:
    """Build output-language guidance for the agent prompt."""
    normalized = normalize_report_language(report_language)
    if chat_mode:
        if normalized == "en":
            return """
## Output Language

- Reply in English.
- If you output JSON, keep the keys unchanged and write every human-readable value in English.
"""
        return """
## 输出语言

- 默认使用中文回答。
- 若输出 JSON，键名保持不变，所有面向用户的文本值使用中文。
"""

    if normalized == "en":
        return """
## Output Language

- Keep every JSON key unchanged.
- `decision_type` must remain `buy|hold|sell`.
- All human-readable JSON values must be written in English.
- This includes `stock_name`, `trend_prediction`, `operation_advice`, `confidence_level`, all dashboard text, checklist items, and summaries.
"""

    return """
## 输出语言

- 所有 JSON 键名保持不变。
- `decision_type` 必须保持为 `buy|hold|sell`。
- 所有面向用户的人类可读文本值必须使用中文。
"""


# ============================================================
# Agent Executor
# ============================================================

class AgentExecutor:
    """ReAct agent loop with tool calling.

    Usage::

        executor = AgentExecutor(tool_registry, llm_adapter)
        result = executor.run("Analyze stock 600519")
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        llm_adapter: LLMToolAdapter,
        skill_instructions: str = "",
        default_skill_policy: str = "",
        max_steps: int = 10,
        timeout_seconds: Optional[float] = None,
    ):
        self.tool_registry = tool_registry
        self.llm_adapter = llm_adapter
        self.skill_instructions = skill_instructions
        self.default_skill_policy = default_skill_policy
        self.max_steps = max_steps
        self.timeout_seconds = timeout_seconds

    def run(self, task: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        """Execute the agent loop for a given task.

        Args:
            task: The user task / analysis request.
            context: Optional context dict (e.g., {"stock_code": "600519"}).

        Returns:
            AgentResult with parsed dashboard or error.
        """
        # Build system prompt with skills
        skills_section = ""
        if self.skill_instructions:
            skills_section = f"## 激活的研究观察规则\n\n{self.skill_instructions}"
        default_skill_policy_section = ""
        if self.default_skill_policy:
            default_skill_policy_section = f"\n{self.default_skill_policy}\n"
        report_language = normalize_report_language((context or {}).get("report_language", "zh"))
        system_prompt = AGENT_SYSTEM_PROMPT.format(
            default_skill_policy_section=default_skill_policy_section,
            skills_section=skills_section,
            language_section=_build_language_section(report_language),
        )

        # Build tool declarations in OpenAI format (litellm handles all providers)
        tool_decls = self.tool_registry.to_openai_tools()

        # Initialize conversation
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": self._build_user_message(task, context)},
        ]

        owner_id = str((context or {}).get("owner_id") or "").strip() or None
        guest_bucket_hash = str((context or {}).get("guest_bucket_hash") or "").strip() or None
        return self._run_loop(
            messages,
            tool_decls,
            parse_dashboard=True,
            owner_user_id=owner_id,
            guest_bucket_hash=guest_bucket_hash,
        )

    def chat(
        self,
        message: str,
        session_id: str,
        progress_callback: Optional[Callable] = None,
        context: Optional[Dict[str, Any]] = None,
        owner_id: Optional[str] = None,
    ) -> AgentResult:
        """Execute the agent loop for a free-form chat message.

        Args:
            message: The user's chat message.
            session_id: The conversation session ID.
            progress_callback: Optional callback for streaming progress events.
            context: Optional context dict from previous analysis for data reuse.

        Returns:
            AgentResult with the text response.
        """
        from src.agent.conversation import conversation_manager

        # Build system prompt with skills
        skills_section = ""
        if self.skill_instructions:
            skills_section = f"## 激活的研究观察规则\n\n{self.skill_instructions}"
        default_skill_policy_section = ""
        if self.default_skill_policy:
            default_skill_policy_section = f"\n{self.default_skill_policy}\n"
        report_language = normalize_report_language((context or {}).get("report_language", "zh"))
        system_prompt = CHAT_SYSTEM_PROMPT.format(
            default_skill_policy_section=default_skill_policy_section,
            skills_section=skills_section,
            language_section=_build_language_section(report_language, chat_mode=True),
        )

        # Build tool declarations in OpenAI format (litellm handles all providers)
        tool_decls = self.tool_registry.to_openai_tools()

        # Get conversation history
        session = conversation_manager.get_or_create(session_id, owner_id=owner_id)
        history = session.get_history()

        # Initialize conversation
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
        ]
        messages.extend(history)

        # Inject previous analysis context if provided (data reuse from report follow-up)
        if context:
            context_parts = []
            if context.get("stock_code"):
                context_parts.append(f"股票代码: {context['stock_code']}")
            if context.get("stock_name"):
                context_parts.append(f"股票名称: {context['stock_name']}")
            if context.get("previous_price"):
                context_parts.append(f"上次分析价格: {context['previous_price']}")
            if context.get("previous_change_pct"):
                context_parts.append(f"上次涨跌幅: {context['previous_change_pct']}%")
            if context.get("previous_analysis_summary"):
                summary = context["previous_analysis_summary"]
                summary_text = json.dumps(summary, ensure_ascii=False) if isinstance(summary, dict) else str(summary)
                context_parts.append(f"上次分析摘要:\n{summary_text}")
            if context.get("previous_strategy"):
                strategy = context["previous_strategy"]
                strategy_text = json.dumps(strategy, ensure_ascii=False) if isinstance(strategy, dict) else str(strategy)
                context_parts.append(f"上次策略分析:\n{strategy_text}")
            stock_chat = context.get("stock_chat")
            if isinstance(stock_chat, dict):
                selected_lens = stock_chat.get("selected_lens")
                smart_route = stock_chat.get("smart_route")
                data_context = stock_chat.get("data_context")
                stock_context = stock_chat.get("stock_context")
                answer_sections = stock_chat.get("answer_sections")
                instruction = stock_chat.get("instruction")
                route_text = json.dumps(smart_route, ensure_ascii=False) if isinstance(smart_route, dict) else ""
                data_text = json.dumps(data_context, ensure_ascii=False) if isinstance(data_context, list) else ""
                stock_context_text = json.dumps(stock_context, ensure_ascii=False) if isinstance(stock_context, dict) else ""
                stock_evidence_summary = _compact_stock_evidence_summary(stock_context) if isinstance(stock_context, dict) else ""
                sections_text = " / ".join(str(item) for item in answer_sections) if isinstance(answer_sections, list) else ""
                context_parts.append(
                    "[Stock Chat 输出契约]\n"
                    f"分析视角: {selected_lens or '综合判断'}\n"
                    f"Smart Route: {route_text or '未识别'}\n"
                    f"数据上下文: {data_text or '未检查'}\n"
                    f"回答结构: {sections_text or '结论 / 关键依据 / 关键价位 / 风险边界 / 观察计划 / 数据可信度'}\n"
                    f"约束: {instruction or '数据缺失必须说明，不承诺确定性收益。'}"
                )
                if stock_context_text:
                    context_parts.append(
                        "[Stock Chat 证据摘要]\n"
                        f"{stock_evidence_summary or stock_context_text}\n"
                        "使用规则: 只能引用此处标记为 available/partial/stale/fallback/used 的证据；"
                        "未知、缺失或未检查的数据必须明确说明，不能补写成已验证事实；"
                        "不能声称使用了 unavailable/unknown/missing 的行情、技术、基本面或新闻数据；"
                        "如果暴露状态证据已知，必须区分未持有与已持有状态参考；"
                        "如果大多数数据 unknown/missing，避免强确定性结论。"
                    )
            if context_parts:
                context_msg = "[系统提供的历史分析上下文，可供参考对比]\n" + "\n".join(context_parts)
                messages.append({"role": "user", "content": context_msg})
                messages.append({"role": "assistant", "content": "好的，我已了解该股票的历史分析数据。请告诉我你想了解什么？"})

        messages.append({"role": "user", "content": message})

        # Persist the user turn immediately so the session appears in history during processing
        if owner_id is None:
            conversation_manager.add_message(session_id, "user", message)
        else:
            conversation_manager.add_message(session_id, "user", message, owner_id=owner_id)

        result = self._run_loop(
            messages,
            tool_decls,
            parse_dashboard=False,
            progress_callback=progress_callback,
            owner_user_id=owner_id,
        )

        # Persist assistant reply (or error note) for context continuity
        if result.success:
            if owner_id is None:
                conversation_manager.add_message(session_id, "assistant", result.content)
            else:
                conversation_manager.add_message(session_id, "assistant", result.content, owner_id=owner_id)
        else:
            error_note = f"[分析失败] {result.error or '未知错误'}"
            if owner_id is None:
                conversation_manager.add_message(session_id, "assistant", error_note)
            else:
                conversation_manager.add_message(session_id, "assistant", error_note, owner_id=owner_id)

        return result

    def _run_loop(
        self,
        messages: List[Dict[str, Any]],
        tool_decls: List[Dict[str, Any]],
        parse_dashboard: bool,
        progress_callback: Optional[Callable] = None,
        *,
        owner_user_id: Optional[str] = None,
        guest_bucket_hash: Optional[str] = None,
    ) -> AgentResult:
        """Delegate to the shared runner and adapt the result.

        This preserves the exact same observable behaviour as the original
        inline implementation while sharing the single authoritative loop
        in :mod:`src.agent.runner`.
        """
        loop_result = run_agent_loop(
            messages=messages,
            tool_registry=self.tool_registry,
            llm_adapter=self.llm_adapter,
            max_steps=self.max_steps,
            progress_callback=progress_callback,
            max_wall_clock_seconds=self.timeout_seconds,
            owner_user_id=owner_user_id,
            guest_bucket_hash=guest_bucket_hash,
        )

        model_str = loop_result.model

        if parse_dashboard and loop_result.success:
            dashboard = parse_dashboard_json(loop_result.content)
            return AgentResult(
                success=dashboard is not None,
                content=loop_result.content,
                dashboard=dashboard,
                tool_calls_log=loop_result.tool_calls_log,
                total_steps=loop_result.total_steps,
                total_tokens=loop_result.total_tokens,
                provider=loop_result.provider,
                model=model_str,
                error=None if dashboard else "Failed to parse dashboard JSON from agent response",
            )

        return AgentResult(
            success=loop_result.success,
            content=loop_result.content,
            dashboard=None,
            tool_calls_log=loop_result.tool_calls_log,
            total_steps=loop_result.total_steps,
            total_tokens=loop_result.total_tokens,
            provider=loop_result.provider,
            model=model_str,
            error=loop_result.error,
        )

    def _build_user_message(self, task: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Build the initial user message."""
        parts = [task]
        if context:
            report_language = normalize_report_language(context.get("report_language", "zh"))
            if context.get("stock_code"):
                parts.append(f"\n股票代码: {context['stock_code']}")
            if context.get("report_type"):
                parts.append(f"报告类型: {context['report_type']}")
            if report_language == "en":
                parts.append("输出语言: English（所有 JSON 键名保持不变，所有面向用户的文本值使用英文）")
            else:
                parts.append("输出语言: 中文（所有 JSON 键名保持不变，所有面向用户的文本值使用中文）")

            # Inject pre-fetched context data to avoid redundant fetches
            if context.get("realtime_quote"):
                parts.append(f"\n[系统已获取的实时行情]\n{json.dumps(context['realtime_quote'], ensure_ascii=False)}")
            if context.get("chip_distribution"):
                parts.append(f"\n[系统已获取的筹码分布]\n{json.dumps(context['chip_distribution'], ensure_ascii=False)}")
            if context.get("news_context"):
                parts.append(f"\n[系统已获取的新闻与舆情情报]\n{context['news_context']}")

        parts.append("\n请使用可用工具获取缺失的数据（如历史K线、新闻等），然后以研究观察仪表盘 JSON 格式输出分析结果。")
        return "\n".join(parts)
