# Data Coverage Consumer Projection Examples

These examples show product-language outcomes for consumer-facing WolfyStock
surfaces. They are written as user-visible states, not diagnostic notes.

## Market Overview

Status: `AVAILABLE`

- 用户看到：市场概览可正常查看。
- 页面文案：不额外提示。
- 新鲜度表达：显示最近更新时间即可。

## Liquidity

Status: `PARTIAL`

- 用户看到：流动性页面仍可查看，但部分信号暂时不完整。
- 页面文案：`部分数据暂不可用。`
- 新鲜度表达：保留最近更新时间，避免展开解释。

## Scanner

Status: `INSUFFICIENT`

- 用户看到：候选结果只能作为观察参考，当前不适合强化判断。
- 页面文案：`当前信号置信度较低，仅供观察。`
- 新鲜度表达：保留最近更新时间，不扩展内部原因。

## Portfolio

Status: `DELAYED`

- 用户看到：组合页沿用最近一次可用行情，适合继续观察，不应误读为实时更新。
- 页面文案：`已使用最近一次可用数据。`
- 新鲜度表达：明确显示最近更新时间。

## Backtest

Status: `UNAVAILABLE`

- 用户看到：本次回测结果当前不可展示，需要稍后再试。
- 页面文案：`本模块暂不可用，请稍后重试。`
- 新鲜度表达：如果页面已有时间上下文，可继续显示最近更新时间。

## Copy Pattern

- 优先展示一个产品状态，再补一条简短说明。
- 优先说明用户现在能否继续使用，而不是解释后台细节。
- 优先用最近更新时间建立预期，而不是堆叠说明。
