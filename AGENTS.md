# AGENTS.md

本文件是本仓库 AI 协作规则的唯一真源。更完整的项目手册由
`scripts/build_ai_project_manual.py` 生成到 `docs/AI_PROJECT_MANUAL.md`。
如果本文件、用户当前提示、代码现状或脚本结果冲突，优先级为：
当前用户明确要求 -> 本文件 -> 可执行代码/脚本/测试 -> 其他说明。

## 硬规则

- 遵循目录边界：
  - 后端：`src/`、`data_provider/`、`api/`、`bot/`
  - Web：`apps/dsa-web/`
  - Desktop：`apps/dsa-desktop/`
  - 脚本/部署/CI：`scripts/`、`.github/workflows/`、`docker/`
- 未经当前任务明确授权，不执行 `git commit`、`git tag`、`git push`、
  `git merge`、`git rebase`、删除分支或删除 worktree。
- 若任务明确授权 commit / integration / cleanup，也必须先完成验证、检查
  diff/status、确认无冲突/无意外文件/无密钥，再执行授权动作。
- commit message 使用英文，不添加 `Co-Authored-By`。
- 不写死密钥、账号、token、私有 URL、模型名、端口、绝对本机路径或环境差异逻辑。
- 不修改任务范围外文件；不要顺手重构、移动、删除或格式化无关文件。
- 不新增平行实现；优先复用已有模块、配置入口、脚本和测试。
- 新增或改变配置项时，同步 `.env.example` 和相关说明。
- 用户可见行为、CLI/API 行为、部署方式、通知方式、报告结构或文档模型变化，
  应更新 `README.md`、`docs/AI_PROJECT_MANUAL.md` 的生成源，或任务指定的
  canonical 文档位置。

## 受保护域

除非当前任务明确授权并给出验证路径，否则不要修改：

- provider 适配、provider 顺序、fallback、缓存/新鲜度、source authority、凭证和外部网络行为
- scanner 打分、筛选、排序、阈值、score 贡献和 live/fallback 标签
- backtest fills、成本、指标、benchmark、参数/赢家语义、universe 与 stored result 语义
- portfolio 账户、现金、持仓、交易、P&L、FX、cost basis、broker sync/import 与 ledger 语义
- auth/RBAC/security、session、cookie、CSRF/CORS、token/password、MFA、admin 保护
- DB migration、root config、依赖/lockfile、CI、发布流程
- broker/order 执行、买卖/加减仓/目标价/仓位建议等交易建议

不要引入 fake data、fallback payload、placeholder readiness、隐藏兼容层、raw provider
泄漏、交易建议或一次性 Markdown 报告来满足任务。

## 默认工作流

1. 先做只读发现：确认 `pwd`、branch、`git status --short --branch`，阅读当前提示、
   本文件、`README.md`、`docs/AI_PROJECT_MANUAL.md` 和最小相关源码/测试。
2. 判断改动面：docs / backend / frontend / API/schema / provider / auth /
   portfolio / backtest / workflow / review。
3. 保持最小必要改动；复杂度或风险上升时先收敛范围再继续。
4. 运行能证明当前改动的最小验证集，不用无关测试堆砌“完整感”。
5. 完成前检查 `git diff`、`git status`、必要的 secret/link/format 检查。

## Worktree 环境

- 在任意 checkout 运行 `./wolfy bootstrap --ensure`，构建或复用 OS cache root 下经过验证的 content-addressed Python 与 Web snapshots；worktree 不得链接另一个 checkout 的 mutable dependency 目录。
- Python direct intent 由 `requirements.txt` 与 `requirements-dev.txt` 保存；`requirements-lock.json` 及其 CPython 3.11/3.12 lock family 是唯一 install authority。权威矩阵支持 CPython 3.11 Linux x86_64 runtime/development、Linux aarch64 runtime（Docker `linux/arm64` 归一化身份）、macOS arm64/x86_64 与 Windows AMD64 runtime/development，以及 CPython 3.12 macOS arm64/x86_64 与 Windows AMD64 runtime/development；不在矩阵内的 target/profile 必须在安装前失败。运行 `./wolfy lock python --check` 检查 freshness、pins、target artifact filenames/hashes、sdist build requirements、resolver 和完整 target matrix。
- 只有显式依赖审查可运行 `./wolfy lock python --update`；该命令固定使用 `uv 0.11.19` 作为 resolver，必须审查 direct/transitive diff，且 bootstrap、test、dev、CI、release qualification 不得隐式更新 lock。
- 无网络模式使用 `./wolfy bootstrap --ensure --offline`；缺少已验证 snapshot 或 locked artifact cache material 时必须显式失败。Linux `arm64` 与 `aarch64` 必须归一到同一 reviewed runtime projection。在线/离线 bootstrap 必须选择同一 target/profile graph 和 artifact projection，并使用 hash verification，禁止回退到 requirements resolution。
- Release container 必须按 BuildKit `TARGETARCH` 复用同一 Python lock authority：`amd64` 选择 Linux x86_64 CPython 3.11 runtime，`arm64` 选择 Linux aarch64 CPython 3.11 runtime；只允许 `--no-deps --require-hashes --no-build-isolation` 的 reviewed lock 安装，禁止 requirements intent、development lock、uv 或其他 resolver 进入镜像依赖安装路径。
- `bash scripts/bootstrap_worktree.sh --check` 与 `--apply` 仅是 `./wolfy env verify` 和 `./wolfy bootstrap --ensure` 的兼容 delegate，不拥有独立 fingerprint、安装或链接逻辑。

## 常用命令

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

验证：

```bash
./scripts/ci_gate.sh
./wolfy lock python --check
./wolfy exec --profile test -- python -m pytest -m "not network"
python -m py_compile <changed_python_files>
./wolfy exec --profile test -- npm --prefix apps/dsa-web run lint
./wolfy exec --profile test -- npm --prefix apps/dsa-web run build
cd apps/dsa-desktop && npm install && npm run build
python scripts/build_ai_project_manual.py --check
python scripts/check_ai_assets.py
```

> Shell 说明：`scripts/*.sh` 与 `$(git rev-parse HEAD)` 是 POSIX shell
> （bash/sh）语法。Windows 请在 Git Bash、WSL 或提供 POSIX `sh` 的shell 中运行，
> 例如 `bash scripts/ci_gate.sh`。PowerShell 同样支持 `$(...)` 子表达式语法。

## AI 协作资产

- `CLAUDE.md` 必须保持为指向 `AGENTS.md` 的软链接。
- `.github/copilot-instructions.md` 与 `.github/instructions/*.instructions.md`
  是 GitHub/Copilot 镜像说明；若冲突，以本文件为准。
- `.claude/skills/` 是仓库内保留的 skill 资产；`.claude/reviews/` 是本地分析产物。
- `docs/AI_PROJECT_MANUAL.md` 是生成文件；需要改手册内容时，修改
  `scripts/build_ai_project_manual.py` 或 tiny canonical source，再运行生成器。
- 修改 AI 协作治理资产时，运行 `python scripts/check_ai_assets.py`。

## 交付要求

最终说明应包含改了什么、为什么、验证情况、未验证项、风险、回滚方式和最终
`git status`。若创建 commit，报告 commit hash；若任务禁止 push，则不要 push。
