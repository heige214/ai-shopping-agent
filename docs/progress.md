# 项目进度日志

> 用途：每个模块 / 窗口结束时更新一次，给下一个窗口做交接。
> 规则：只记事实，不重复设计文档；接口、DB 契约变更先改设计文档，再改这里。
> 最新记录放最上面。

最后更新：2026-11-13

## 当前状态

| 里程碑 | 内容 | 状态 | 最近提交 |
|---|---|---|---|
| M0 | 项目骨架：配置、DB、认证、前端壳、测试基线 | 已完成 | m0 |
| M1 | 商品域 + 种子数据 + 商品详情 | 未开始 | — |
| M2 | 购物车、地址、订单、模拟支付/发货 | 未开始 | — |
| M3 | 知识库 + RAG 商品客服 | 未开始 | — |
| M4 | 导购聊天、意图槽位、澄清、尺码 | 未开始 | — |
| M5 | 图片理解、语音、AI 加购 | 未开始 | — |
| M6 | 转人工、客服端队列/工作台 | 未开始 | — |
| M7 | 知识提炼、审核、入库 | 未开始 | — |
| M8 | 评测集、消融实验、指标 | 未开始 | — |
| M9 | 部署、论文材料、演示排练 | 未开始 | — |

状态只用：未开始 / 进行中 / 已完成 / 阻塞。

## 当前阻塞

- 无。

## 模块记录

<!-- 每完成一个模块，把记录加在这里的最上面；第一条从 M0 开始。 -->

## 2026-11-13 · M0 项目骨架

- 状态：已完成
- 本次目标：搭好前后端骨架，打通登录链路，登录后显示「AI 找货 / 我的」两个 Tab。
- 完成内容：
  - 后端：FastAPI + PostgreSQL + Alembic；users 表；注册、登录、当前用户接口；健康检查；演示账号种子脚本；422 校验失败脱敏。
  - 前端：Vue 3 + Vite + TypeScript + Vant 4；登录/注册页；双 Tab 布局；鉴权路由守卫；Axios 自动带 token 与 401 退出；会话过期事件处理。
  - 测试：pytest 48 项（14 安全 + 29 认证/API + 1 迁移 + 1 健康 + 3 种子）；Playwright 2 项（登录后双 Tab 流程、未登录深链接回跳）。
  - 工程：git 初始化；`.gitignore` 排除商品图与 node_modules；Docker 开发数据库；README；本地开发端口适配为 8100；文档：设计文档 §13.3 环境变量名与实现对齐（JWT_SECRET_KEY）。
- 改动文件 / 目录：
  - `backend/app/`、`backend/alembic/`、`backend/scripts/`、`backend/tests/`
  - `frontend/src/`、`frontend/tests/e2e/`、`frontend/playwright.config.ts`、`frontend/vite.config.ts`
  - `deploy/docker-compose.dev.yml`、`deploy/initdb/`
  - `.gitignore`、`README.md`、`docs/`
- DB 迁移：`20261113_0001_create_users`
- 新增环境变量：`DATABASE_URL`、`TEST_DATABASE_URL`、`JWT_SECRET_KEY`、`JWT_ALGORITHM`、`JWT_EXPIRE_MINUTES`、`CORS_ORIGINS`
- 测试与验收：
  - 命令：`cd backend && source .venv/Scripts/activate && python -m pytest -v`；`cd frontend && npm run build`；`cd frontend && npm run test:e2e`
  - 结果：后端 `48 passed`（16.91s）；前端构建成功（vue-tsc 无报错，Vite 378 modules，2.40s）；E2E `2 passed`（5.5s，含用户资料卡断言）；手工验收 6 步通过（真实浏览器 Playwright 抽查：未登录重定向、demo 登录、双 Tab、我的页资料与退出、退出回登录、刷新仍在登录页）。
- 遗留问题：
  - [后续] 登录态为 localStorage JWT，无 refresh token；改密码/找回密码/OAuth/限流均未实现。
  - [后续] `PATCH /api/users/me` 个人资料编辑未实现。
  - [后续] 统一业务错误码、SSE/WebSocket 契约留到后续模块。
  - [M1 前] `backend/static/products` 本地备份仍未执行。
  - [后续] Vant 全量引入导致首屏包偏大（JS 主包约 143.40 kB gzip、CSS 约 53.49 kB gzip），后续按需引入优化。
  - [后续] 部分设计 token 组合对比度偏低（WCAG）；登录/注册页存在重复 CSS；favicon 404、iOS 输入聚焦缩放未处理。
  - [后续] 网络异常且保留 token 时，首页问候语/我的页姓名为空，后续补加载/失败态。
  - [备注] Playwright 固定 1.64.1 以匹配本机 chromium-1248；换机后需 `npx playwright install chromium`。
  - [低] README 的 `.env` 脚本对带引号空值 `JWT_SECRET_KEY=""` 会误判为已配置（边缘情况）。
- 下一模块依赖：M1 可直接复用 users 表、`get_current_user` 依赖、Axios 客户端、Pinia 认证 store、双 Tab 布局；后端本地端口 8100，前端代理已指向该端口。
- commit：`m0` tag（M0 提交范围 `190bdb5..m0`；实现提交见 `git log`）

## 记录模板（复制用）

```markdown
## YYYY-MM-DD · Mx 模块名

- 状态：已完成 / 进行中 / 阻塞
- 本次目标：
- 完成内容：
- 改动文件 / 目录：
- DB 迁移：
- 新增环境变量：
- 测试与验收：
  - 命令：
  - 结果：
- 遗留问题：
- 下一模块依赖：
- commit：
```

## 维护约定

1. 每个模块 / 窗口结束前必须更新一次，并提交 git。
2. 只写“做了什么、怎么验证、还差什么”，不要复制设计文档的大段内容。
3. 如果改动涉及 API DTO、错误码、DB 字段或路由，先更新设计文档，再在记录里注明“契约已变更”。
4. 下一个窗口开场读：`docs/implementation-handoff.md` + 本文件 + 设计文档相关章节。
