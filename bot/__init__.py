# -*- coding: utf-8 -*-
"""
===================================
机器人命令触发系统
===================================

通过 @机器人 或发送命令触发股票分析等功能。
当前代码真值：
- 命令机器人平台注册仅包含钉钉 Webhook。
- 钉钉/飞书另有可选 Stream 客户端。
- Discord 仍保留通知发送配置，但不属于本模块的活跃命令入口。

模块结构：
- models.py: 统一的消息/响应模型
- dispatcher.py: 命令分发器
- commands/: 命令处理器
- platforms/: 平台适配器
- handler.py: Webhook 处理器

使用方式：
1. 配置环境变量（当前命令入口以钉钉为主）
2. 启动 WebUI 服务
3. 手动挂载并配置钉钉 Webhook URL：
   - 钉钉: http://your-server/bot/dingtalk
4. 如需扩展其他平台，需先补平台适配器并注册到 `ALL_PLATFORMS`

支持的命令：
- /analyze <股票代码>  - 分析指定股票
- /market             - 大盘复盘
- /batch              - 批量分析自选股
- /help               - 显示帮助
- /status             - 系统状态
"""

from bot.models import BotMessage, BotResponse, ChatType, WebhookResponse
from bot.dispatcher import CommandDispatcher, get_dispatcher

__all__ = [
    'BotMessage',
    'BotResponse',
    'ChatType',
    'WebhookResponse',
    'CommandDispatcher',
    'get_dispatcher',
]
