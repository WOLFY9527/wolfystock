# Backend + Frontend Global Audit Report

- Generated at: `2026-04-24`
- Repo: `daily_stock_analysis`
- Branch: `codex/audit_review`
- Audit mode: conservative, subtraction-first, behavior-preserving

## 问题发现

### F1. 已修复: WebUI 生产构建把测试树一起编进来

- Symptom:
  - `python3 main.py --serve-only --host 127.0.0.1 --port 8001` 的启动链路会先执行前端 build。
  - 在审计过程中，这条链路曾因 `apps/dsa-web/src/**/__tests__/**` 下的测试文件参与 `tsc -b` 而被阻断。
- Root cause:
  - `apps/dsa-web/tsconfig.app.json` 仅 `include: ["src"]`，没有把测试文件从生产编译范围中排除。
- Fix:
  - 在 `apps/dsa-web/tsconfig.app.json` 中排除 `src/**/__tests__/**`、`src/**/*.test.ts`、`src/**/*.test.tsx`。
- Result:
  - `main.py --serve-only` 的 auto-build 重新稳定可用，且不会继续被非运行时代码误伤。

### F2. 已修复: `PortfolioPage` 中文 IBKR sync 用例存在异步等待竞争

- Symptom:
  - `apps/dsa-web/src/pages/__tests__/PortfolioPage.test.tsx` 中中文用例在点击 `只读同步 IBKR` 后，先等待静态 `只读` 徽章，再立刻断言 `账户引用:`，会偶发在真正的 `ibkrSyncResult` 渲染前触发失败。
- Root cause:
  - `只读` 徽章是静态面板内容，不是同步完成信号。
- Fix:
  - 把断言改为等待实际同步结果文本出现，再验证本地化文案。
- Result:
  - Portfolio 前端单测恢复稳定。

### F3. 已修复: `Shell` 测试夹具对默认 i18n/admin-mode 状态过于隐式

- Symptom:
  - `apps/dsa-web/src/components/layout/__tests__/Shell.test.tsx` 在部分场景下会把 `nav.signIn` / `nav.adminModeEnter` 之类的 key 当成可见文案，且 admin-mode 切换会触发 `act(...)` 警告。
- Root cause:
  - 测试未显式 mock `useI18n`，对默认 context 和外部 store 切换的依赖太弱。
- Fix:
  - 为 `Shell.test.tsx` 增加显式 i18n mock，并用 `act(...)` 包裹 admin-mode 切换交互。
- Result:
  - Shell 测试稳定，前端总测试恢复全绿。

### F4. 已修复: Playwright smoke 仍按旧版 `/settings = 系统设置` 信息架构断言

- Symptom:
  - `apps/dsa-web/e2e/smoke.spec.ts` 仍假设登录后进入 `/settings` 就应该直接看到 `系统设置`、`重置`、`保存配置`。
  - 这与当前产品已经落地的“`/settings` = 个人设置，`/settings/system` = Admin Mode 下的独立控制台”信息架构不一致。
- Root cause:
  - E2E smoke 断言没有跟上 `PersonalSettingsPage` / `SystemSettingsPage` 分层后的实际路由语义。
- Fix:
  - 把 smoke 改为验证真实流程：
    - 登录后先进入 `/settings` 并确认 `个人偏好`
    - 显式点击 `打开管理工具`
    - 再从主内容区进入 `独立控制台`
    - 最终在 `/settings/system` 断言 `系统控制面`
- Result:
  - 自动化 smoke 叙述与当前 live browser 验证重新对齐，不再把过时 IA 当成线上回归。

### F5. 审计发现未改动: 多个核心模块体量继续过大，后续维护成本高

按代码行数统计的高风险热点:

| File | Lines | Risk |
| --- | ---: | --- |
| `src/services/rule_backtest_service.py` | 8519 | 回测读写、stored-first/legacy fallback、结果重开逻辑高度集中 |
| `src/storage.py` | 6562 | SQLite primary truth、PG coexistence、topology/reporting、runtime bootstrap 高耦合 |
| `src/services/market_scanner_service.py` | 4932 | universe 构建、缓存、provider fallback、scan 汇总过于集中 |
| `apps/dsa-web/src/i18n/core.ts` | 4828 | 双语资源极大，测试和界面文案修改成本高 |
| `apps/dsa-web/src/pages/SettingsPage.tsx` | 4604 | 系统设置/管理工具/数据源密度高 |
| `src/services/portfolio_service.py` | 3848 | snapshot/risk/cache/fx/invalidation/IBKR overlay 集中 |
| `apps/dsa-web/src/pages/PortfolioPage.tsx` | 2369 | UI 状态面复杂，含 IBKR sync、snapshot、event 列表、手工录入 |

## 优化方案

### 已落地的减法式优化

1. 把前端生产 TypeScript build 限定到运行时代码，不再把测试文件当成 runtime 依赖。
2. 修正前端 Playwright smoke 的 Python fallback 为 `python3`，与当前仓库环境一致。
3. 修正两处前端测试不稳定点，而不是修改业务语义去迎合脆弱测试。
4. 把 Playwright smoke 的 settings/admin 断言改为当前真实产品流，消除旧信息架构造成的假失败。
5. 保留 `src/postgres_phase_{a..g}.py`、`docs/architecture/archive/phase-f/*` 等兼容层/归档文档，不做冒险删除。
6. 把新闻 provider fallback 测试的期望日期改为“与运行时一致的本地日期归一化”，消除时区跨日带来的假失败。
7. 把 Real-PG bundle 的 `bootstrap_applied_at` 也纳入瞬时字段归一化，避免 smoke/report 同构比较时出现跨秒 diff。

### 已确认但无需新增代码的后端收敛

1. `Phase F` authority 读路径已经走批量物化：
   - `src/storage.py::_collect_phase_f_portfolio_shadow_authority_states()` 会统一调用 `get_account_shadow_bundles(account_ids=...)`
   - `tests/test_postgres_phase_f.py` 已锁定 account metadata / broker connection metadata / latest sync surface 的单次批量调用
   - 结论：当前主读路径不存在本次提示范围内的逐账户 N+1 authority 物化
2. Real-PG bundle 输出已经做瞬时字段规范化：
   - `src/database_doctor.py::_normalize_real_pg_bundle_report()` 会把临时 SQLite 路径替换为 `<temporary>/database-real-pg-bundle.sqlite`
   - 同时把 `probe_session_id` 归一化为 `<latest_probe_session_id>`，并重建 AI handoff sample
   - `tests/test_database_doctor.py` 已覆盖 deterministic comparison 所需的这些 redaction
3. 兼容 shim 仍属有意保留，而不是待删垃圾：
   - `src/postgres_phase_{a..g}.py` 仍承担 legacy import 兼容层职责
   - 本次只在报告/手册中明确记录，不做破坏性删除

### 建议但未在本次实施的后续优化

1. `src/storage.py`
   - 方向: 继续把纯 report/debug/coordination 辅助逻辑下沉到专门 helper，保持 SQLite primary truth 决策不动。
   - 非目标: 不在当前 slice 内推进 Phase F/G serving truth 变更。
2. `src/services/rule_backtest_service.py`
   - 方向: 先做 benchmark + read-only extractor split，再考虑进一步拆分 reopen/trustworthiness path。
   - 非目标: 不改变 stored-first / legacy fallback 语义。
3. `src/services/market_scanner_service.py`
   - 方向: 以 universe/history cache 和 diagnostics aggregation 为界，先做纯 helper 抽离和 benchmark。
   - 非目标: 不改 scanner ranking/AI additive semantics。
4. `apps/dsa-web` bundle
   - 方向: 继续降低大页面 chunk。
   - 当前 build 仍较大:
     - `PortfolioPage`: `403.52 kB`
     - main app chunk: `364.51 kB`
     - `BacktestPage`: `231.42 kB`
     - `SystemSettingsPage`: `169.07 kB`

## 改动概述

### 本次实际改动

- `apps/dsa-web/tsconfig.app.json`
  - 排除测试树，修复 WebUI runtime build 误编译测试的问题。
- `apps/dsa-web/playwright.config.ts`
  - backend fallback 改为 `python3 main.py --serve-only ...`。
- `apps/dsa-web/src/pages/__tests__/PortfolioPage.test.tsx`
  - 修复中文 IBKR sync 结果等待时序。
- `apps/dsa-web/src/components/layout/__tests__/Shell.test.tsx`
  - 加强 i18n/admin-mode fixture，减少假失败。
- `apps/dsa-web/e2e/smoke.spec.ts`
  - 让 Playwright smoke 跟随当前 personal-settings/admin-console 分层，而不是继续断言旧版 `/settings` 系统控制面。
- `tests/test_search_provider_fallbacks.py`
  - 让 Finnhub/GNews fallback 测试使用与运行时一致的本地日期归一化预期，消除跨时区日界线漂移。
- `src/database_doctor.py`
  - 在 Real-PG bundle 归一化里补充 `bootstrap_applied_at` 瞬时字段占位化，保证 smoke/report 可做 deterministic 对比。
- `tests/test_database_doctor.py`
  - 锁定新的 Real-PG bundle 瞬时字段归一化行为。
- `docs/CHANGELOG.md`
  - 记录本次启动链路与前端测试稳定性修正。

### 本次生成的交付产物

- `backend-frontend-global-audit-report.md`
- `backend-frontend-global-audit-report.json`
- `docs/architecture/backend-frontend-modular-maintenance-handbook.md`

### 本次未做的删除

- 未删除任何已确认仍有兼容价值的核心 runtime 模块。
- 未删除 archive/phase-f 等历史审计文档。
- 未把 `src/postgres_phase_{a..g}.py` 兼容 shim 当成“死代码”删除。
- 未把 `SystemSettingsPage.tsx` / `AdminNav.tsx` 当成重复文件删除；它们当前承载的是已落地的 admin route split。

## 潜在风险

1. 前端大页面 chunk 仍然偏大，后续如果继续加功能，首屏与路由切换成本会继续增长。
2. `ci_gate` 虽通过，但仍提示 `flake8` 未安装；本地 gate 目前依赖 deterministic checks + pytest，而不是完整 flake8 覆盖。
3. 当前本地 smoke 因 auth-disabled 默认态可以全跑通过；如果换到 auth-enabled 环境而又缺少 `DSA_WEB_SMOKE_PASSWORD`，认证分支仍会按设计跳过登录提交流程。

## 验证情况

### 后端

- `python3 -m pytest tests/test_database_doctor.py tests/test_postgres_phase_f.py tests/test_postgres_phase_g.py tests/test_postgres_runtime_real_pg.py -q`
  - Result: `103 passed`
- `python3 -m pytest tests/test_search_provider_fallbacks.py -q`
  - Result: `5 passed`
- `./scripts/ci_gate.sh`
  - Result: `1644 passed, 2 skipped, 1 warning, 113 subtests passed`
  - Gate verdict: `all checks passed`

### 数据库 / Phase F/G

- `python3 scripts/database_doctor_smoke.py --write`
  - Result: PASS
  - Key facts:
    - SQLite primary reachable
    - PG coexistence not configured in live runtime path
    - Phase F serving truth still `sqlite`
    - Phase G live source reminder still `.env`
- `python3 scripts/database_doctor_smoke.py --real-pg-bundle --write`
  - Result: PASS
  - Key facts:
    - Phase A-G store initialization: PASS
    - schema/bootstrap: PASS
    - Phase G shadow verification: PASS
    - safety contract:
      - `sqlite_primary_truth_changed=no`
      - `phase_f_serving_changed=no`
      - `phase_g_live_truth_changed=no`

### 前端

- `npm run lint`
  - Result: PASS
- `npm run test`
  - Result: `65 files passed, 476 tests passed`
- `npm run build`
  - Result: PASS
- `npx playwright test e2e/smoke.spec.ts`
  - Result: `6 passed`
- `python3 main.py --serve-only --host 127.0.0.1 --port 8001`
  - Result: PASS
  - Startup now completes frontend auto-build and serves WebUI successfully

### 浏览器验证

Validated against `http://127.0.0.1:8001`:

- `/`
  - PASS
  - Home loaded, no browser console warnings/errors
- `/settings`
  - PASS
  - Personal settings loaded, admin-tools card visible, no browser console warnings/errors
- `/portfolio`
  - PASS
  - Portfolio loaded, FX status card visible, no browser console warnings/errors
- `/settings/system`
  - PASS
  - Admin mode can be enabled from `/settings`, and the same browser session can open the system control plane
- `/zh/settings/system`
  - PASS
  - Locale-prefixed admin route keeps the same unlocked session state and localized links

## 回滚方案

If you want to roll back only this audit pass and keep the unrelated admin/settings local worktree changes, restore only these files:

```bash
git restore -- \
  apps/dsa-web/tsconfig.app.json \
  apps/dsa-web/playwright.config.ts \
  apps/dsa-web/src/pages/__tests__/PortfolioPage.test.tsx \
  apps/dsa-web/src/components/layout/__tests__/Shell.test.tsx \
  apps/dsa-web/e2e/smoke.spec.ts \
  src/database_doctor.py \
  tests/test_database_doctor.py \
  tests/test_search_provider_fallbacks.py \
  docs/CHANGELOG.md \
  backend-frontend-global-audit-report.md \
  backend-frontend-global-audit-report.json \
  docs/architecture/backend-frontend-modular-maintenance-handbook.md
```

If you also want to discard the generated smoke artifacts from this audit:

```bash
rm -f \
  tmp/database-doctor-report-smoke.md \
  tmp/database-doctor-report-smoke.json \
  tmp/database-real-pg-bundle-smoke.md \
  tmp/database-real-pg-bundle-smoke.json
```

## 结论

- Code/test/startup hardening from this pass: PASS
- Database consistency contract (SQLite primary / Phase F comparison-only / Phase G `.env` live-source): PASS
- Browser smoke across core routes: PASS
- Remaining high-priority follow-up: continue reducing `PortfolioPage` / main app / `SettingsPage` chunk weight without changing current IA or runtime truth semantics
