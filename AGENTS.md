# AGENTS.md

本文件是 WolfyStock 仓库 AI 协作规则的唯一硬规则源。
`docs/AI_PROJECT_MANUAL.md` 是由 `scripts/build_ai_project_manual.py` 生成的项目手册；
`DESIGN.md` 是 consumer frontend 的产品与设计合同。

优先级：

```text
当前任务明确 scope / acceptance criteria
→ 本文件的安全、truth 与受保护域规则
→ 已验证的代码、脚本、测试和生产合同
→ 任务相关 canonical 文档
→ 视觉原型、历史说明和其他参考
```

当前任务只有在明确写出 ownership 和验证路径时，才可授权受保护域修改；任何任务都不得静默削弱安全、数据真实性、fail-closed 或 no-advice 合同。

---

## 1. 仓库边界

- 后端与领域服务：`src/`、`data_provider/`、`api/`、`bot/`
- Web：`apps/dsa-web/`
- Desktop：`apps/dsa-desktop/`
- 脚本、部署和 CI：`scripts/`、`.github/workflows/`、`docker/`
- 文档权威：`README.md`、本文件、`DESIGN.md`、`docs/AI_PROJECT_MANUAL.md` 和 `docs/DOCS_INDEX.md`

不要跨目录复制业务语义、状态映射、provider 逻辑、accounting 逻辑或 auth 逻辑来完成局部任务。

---

## 2. 不可破坏的 truth 合同

```text
unavailable != zero
missing != zero
missing != neutral
stale != fresh
delayed != live
proxy != official
unknown != available
client receipt time != evidence asOf
render time != observation time
consumer eligible != score eligible
research evidence != trading advice
```

不得：

- 用 0、中性或成功状态替代缺失数据；
- 把缓存、代理、延迟或推断数据呈现成官方实时数据；
- 用页面渲染时间或客户端收包时间伪造证据时间；
- 编造指标、候选、因子、置信度、结论、图表序列、时间戳或 fallback payload；
- 将研究结果转换为买卖、持有、目标价、止损、加减仓或配置建议；
- 在 consumer 页面泄漏 raw provider、cache、schema、credential、admin 或内部 enum。

---

## 3. 受保护域

除非当前任务明确授权并给出 focused 与 canonical 验证路径，否则不要修改：

- provider 适配、顺序、fallback、缓存、新鲜度、source authority、凭证和外部网络行为；
- scanner universe、打分、筛选、排序、阈值、score 贡献、candidate generation 和 live/fallback 标签；
- backtest fills、成本、指标、benchmark、参数/赢家语义、universe、执行和 stored result authority；
- portfolio 账户、现金、持仓、交易、P&L、FX、cost basis、broker sync/import、owner isolation 和 ledger；
- auth/RBAC/security、session、cookie、CSRF/CORS、token/password、MFA 和 admin 保护；
- DB migration、root config、依赖/lockfile、CI、发布和部署合同；
- broker/order 执行或任何交易建议语义。

不要引入第二套 router、auth、state mapper、chart framework、UI framework、data authority、provider authority 或平行前端架构。

---

## 4. Mutation boundary

被动页面加载和只读研究路径不得触发：

```text
provider activation
scanner execution
backtest execution
portfolio mutation
watchlist mutation
auth/account mutation
external notification delivery
```

一次用户动作最多触发一次预期状态转换。加载、刷新、深链、浏览器 back/forward 和展示错误状态不得产生隐藏 mutation。

---

## 5. Git 与安全

未经当前任务明确授权，不执行：

- `git commit`、`git tag`、`git push`、`git merge`、`git rebase`；
- 删除分支或 worktree；
- 远程状态修改或 cleanup。

永久禁止作为自动恢复手段：

```text
git reset
git clean
force push
git worktree remove --force
git branch -D
```

若任务授权 commit / integration / cleanup：

1. 先完成约定验证；
2. 检查 exact diff、changed-file ownership 和 `git status`；
3. 确认无冲突、无意外文件、无密钥、无私有路径；
4. 遇到远端移动、基线变化或 gate 失败时停止；
5. 不做 destructive rollback。

Commit message 使用英文，不添加 `Co-Authored-By`。默认一个任务一个本地 commit；是否 amend、push、merge 或 cleanup 由任务明确规定。

不要写死密钥、账号、token、私有 URL、模型名、绝对本机路径或仅为某台机器服务的环境分支。

---

## 6. 默认工作流

### 6.1 读取

先确认：

```bash
pwd
git status --short --branch
```

默认阅读：

1. 当前任务；
2. 本文件；
3. `README.md`；
4. 最小相关源码和测试；
5. 任务相关的 `docs/AI_PROJECT_MANUAL.md` 章节；
6. 前端产品或视觉任务再阅读 `DESIGN.md` 的相关章节和视觉参考。

只有跨域架构、生产 readiness、文档治理或大型 integration 任务才默认阅读完整手册。不要为小修复全仓盲读。

### 6.2 执行

```text
inspect
→ classify
→ execute
→ validate
→ report
```

在一个连续 run 内完成；不要只给计划后暂停。

默认不使用 subagents 或 delegation。只有任务明确授权、ownership 完全独立且运行时支持时才可使用；其输出不能作为验证证据。

### 6.3 Validation Economy

```text
focused reproduction
→ owned tests
→ impacted shared validation
→ typecheck / design / diff
→ broad validation only when a shared boundary changed
```

以下情况通常需要 broad frontend/backend validation：

- dependency / lockfile；
- App/router/auth；
- shared state mapper 或 cross-page primitive；
- global test/runtime harness；
- backend canonical gate；
- 多条 workstream 收敛后的 milestone integration。

页面或局部任务优先验证：direct deep link、refresh、back/forward、目标 viewport、primary interaction、read-only boundary、console/pageerror、focused tests。

Broad baseline red 时必须分类并证明 baseline equivalence；不要修复无关失败，也不要把环境失败当产品失败。

---

## 7. Shell 与运行环境

- `scripts/*.sh` 必须与其声明的平台兼容。
- 面向 macOS operator 的 Bash 脚本必须支持系统 `/bin/bash` 3.2。
- 不得为绕过空数组或可选参数问题关闭 `set -u`；使用可靠初始化和 guarded expansion。
- success 与 failure 路径都必须验证进程、端口、临时文件和 artifact cleanup。
- 不使用宽泛 `pkill`；只终止当前任务拥有的 PID。
- 未知 untracked 文件先检查，不盲删。

常见生成物可按任务规则识别，但不得将生成物清理扩大到业务文件或用户数据。

---

## 8. 文档治理

- `CLAUDE.md` 必须保持为指向 `AGENTS.md` 的软链接。
- `.github/copilot-instructions.md` 与 `.github/instructions/*.instructions.md` 是镜像说明；冲突时以本文件为准。
- `.claude/skills/` 是仓库 skill 资产；`.claude/reviews/` 是本地分析产物，不是 canonical 项目知识。
- `docs/AI_PROJECT_MANUAL.md` 是生成文件；修改其内容时应更新 `scripts/build_ai_project_manual.py` 或 tiny canonical sources，再运行生成器。
- 不恢复 broad docs index、archive、task-report 或每任务 Markdown 报告。
- 只有命令、公共合同、架构、部署、operator procedure、通知、报告结构或长期产品语义改变时才更新 durable docs；普通局部实现不制造文档 churn。
- 修改 AI 治理资产时运行 `python scripts/check_ai_assets.py`。

---

## 9. 常用命令

运行：

```bash
python main.py
python main.py --debug
python main.py --dry-run
python main.py --stocks 600519,hk00700,AAPL
python main.py --market-review
python main.py --schedule
python main.py --serve
python main.py --serve-only
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

验证按改动范围选择：

```bash
./scripts/ci_gate.sh
python -m pytest -m "not network"
python -m py_compile <changed_python_files>
cd apps/dsa-web && npm ci && npm run lint && npm run typecheck && npm run build
cd apps/dsa-desktop && npm install && npm run build
python scripts/build_ai_project_manual.py --check
python scripts/check_ai_assets.py
```

Vitest 必须从 `apps/dsa-web` 目录运行，确保项目配置和 jsdom 环境生效。

`npm audit --json` 在存在 advisory 时可返回非零；应单独捕获退出码并解析 severity，不要在读取证据前中止。

---

## 10. 交付要求

最终报告必须如实包含：

```text
verdict
root cause / rationale
exact changes
exact changed files
validation commands and results
unverified items
remaining risks
rollback boundary
git branch / commit / ahead-behind / tree / push state
next action
```

没有真实验证证据时，不得报告 `PASS`、`READY_TO_LAND`、`LANDED` 或等价结论。
