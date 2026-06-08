# Discord 通知发送配置

这个文档保留原文件名，但当前只描述 **Discord 通知发送** 的真实配置方式。

## 当前真值

- Discord 仍然是有效的通知目标。
- 当前发送实现位于 `src/notification.py` 和 `src/notification_sender/discord_sender.py`。
- 实际发送方式是 `requests` 调用 Discord Webhook 或 Discord REST API。
- 当前仓库没有可验证的 Discord 命令机器人接入：
  - 没有活跃的 `DiscordPlatform` 注册
  - 没有 Slash Command 接线
  - 没有 `python main.py --discord-bot` 启动模式

## 支持的发送模式

### 1. Webhook 模式

适合只需要把分析结果推送到某个频道的场景。

配置：

```env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

### 2. Bot Token 发送模式

适合需要使用 Bot 身份向指定频道发消息的场景。当前实现仍然是出站 REST 发送，不是交互式命令机器人。

配置：

```env
DISCORD_BOT_TOKEN=your-discord-bot-token
DISCORD_MAIN_CHANNEL_ID=your-channel-id
DISCORD_BOT_STATUS=A股智能分析 | /help
```

## 如何准备 Bot Token 和频道 ID

### 1. 创建 Discord 应用

访问 [Discord Developer Portal](https://discord.com/developers/applications)，创建一个应用并添加 Bot。

### 2. 获取 Bot Token

在 Bot 页面生成并复制 Token，作为 `DISCORD_BOT_TOKEN`。

### 3. 将 Bot 加入服务器

在 `OAuth2 > URL Generator` 中选择 `bot` scope，并授予最小必要权限，例如：

- `Send Messages`
- `Embed Links`
- `Attach Files`
- `Read Message History`

### 4. 获取频道 ID

在 Discord 客户端打开开发者模式，然后右键目标频道，复制频道 ID，作为 `DISCORD_MAIN_CHANNEL_ID`。

## Webhook 获取方式

如果只使用 Webhook：

1. 打开频道设置
2. 进入 `集成 > Webhooks`
3. 创建 Webhook
4. 复制 URL 到 `DISCORD_WEBHOOK_URL`

## 当前不应假定存在的能力

以下能力当前不应被视为仓库真值：

- Discord Slash Commands
- 通过 `bot/` 模块接收 Discord 命令
- 独立 Discord bot 进程或 `--discord-bot` 启动参数

## 故障排查

- **Webhook 发送失败**：检查 `DISCORD_WEBHOOK_URL` 是否正确，频道 Webhook 是否仍有效
- **Bot Token 发送失败**：检查 `DISCORD_BOT_TOKEN`、`DISCORD_MAIN_CHANNEL_ID` 和频道权限
- **没有收到通知**：确认当前运行的分析/通知进程已经加载上述环境变量

## 相关链接

- [Discord Developer Portal](https://discord.com/developers/applications)
- [Discord API Documentation](https://discord.com/developers/docs/intro)
