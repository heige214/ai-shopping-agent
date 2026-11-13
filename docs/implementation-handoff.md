# 实施计划交接（2026-11-13）

## 当前状态

- 设计文档：`docs/superpowers/specs/2026-11-11-ai-shopping-agent-design.md`
  - §18 已标记「评审完成」，6 项评审全部通过。
- 页面样板（已确认，静态无功能）：
  - `docs/mockups/screens-user-part1.png`：登录、AI 导购空状态/对话、商品详情、AI 客服、知识库未命中、排队、人工会话
  - `docs/mockups/screens-user-part2.png`：购物车、结算、订单、我的
  - `docs/mockups/screens-agent.png`：客服端队列、会话工作台、知识审核
  - HTML 源文件与 `mockup.css` 在同一目录。
- 商品图片：`backend/static/products` 共 300 张（4 个一级品类 × 75），鞋靴 75 张已补齐。
- 前置状态（2026-11-13）：`git` 已初始化；M0 已完成；商品图本地备份尚未执行。
- 主项目骨架已完成（M0）：认证、双 Tab 空壳、数据库迁移与测试基线可用；下一步进入 M1 商品域。
- 本地开发端口：后端 8100（本机 Windows 保留 7997–8096，8000 不可用），前端 Vite 5175（避开本机其他项目常占用的 5173/5174），`/api` 代理指向 8100。
- 本地运行：以 `README.md` 的「本地启动」为准（Docker DB 5433、后端 8100、前端 5175、demo/demo123）。

## 已确认范围

- 用户端 H5，两个导航：AI 找货（默认）、我的；发现入口放在聊天空状态。
- 商品详情底部栏「客服」入口；不做全局悬浮客服。
- AI 客服 + 知识库未命中兜底 + 转人工排队 + 人工会话。
- 客服端桌面 Web：队列、会话工作台、知识审核。
- 模拟交易：购物车、地址、订单、模拟支付、模拟发货、确认收货。
- 知识闭环：会话提炼 → 人工审核 → 入库 → 审计。
- 多模态：图片理解、语音转写。
- 前端视觉：以 `docs/mockups/screens-user-part1.png`、`screens-user-part2.png`、`screens-agent.png`、`mockup.css` 和设计文档 §11.1.9 为准；只参考布局与视觉，不复制 mockup 的 HTML/CSS，统一用 Vue 3 + Vant 4 重写。
- M0 页面范围：只做登录页、注册页、「AI 找货」空壳、「我的」空壳；其余用户端页面和 3 个客服端页面按里程碑逐步实现。
- 参考登录模块 `D:\develop\功能模块\登录注册模块` 只读参考、不修改；只借用 JWT Bearer、Axios 拦截器、Pinia store、路由守卫的组织方式，不引入 Element Plus 界面、邮箱验证码、OAuth、refresh token 轮换、登录限流、SQLite 测试库。
- 不做：Agent Assist、真实支付/物流/退款/售后、全自主 ReAct、多租户/多仓/优惠券/商品评价、原生 App/小程序/PWA 打包（只做移动端 H5）、高并发/多实例部署。

## 实施计划默认值（聊天中已提出，用户未反对，按此写）

- 客服端只做桌面 Web；单客服演示账号。
- 一个客服最多同时接 3 个会话，按 FIFO 排队。
- 客服掉线超过 2 分钟，工单自动回队列；无客服在线时提示离线留言。
- 用户关闭页面不等于结束会话，30 分钟无消息才自动结束。
- 种子数据规模：300 商品、3000~5000 SKU、600~900 条商品 FAQ。
- 排期按设计文档 §15 的 26 周（23 周开发 + 3 周缓冲），实施计划先拆 M0~M2。
- 演示保障：一键重置脚本、AI 超时降级、关键路径提前预热、录屏备份。

## 实施计划必须覆盖的落地项

1. 接口契约：DTO、统一错误码、幂等规则、SSE 重连、WebSocket 补消息。
2. 种子数据：商品 JSON、SKU 生成、尺码表、FAQ/政策、知识审核 CSV。
3. 状态机边界：订单超时/取消/库存恢复；工单排队/接入/掉线/关闭；加购动作幂等。
4. 测试与评测：单元/集成/E2E、10 条固定演示路径、指标报告。
5. 部署与运维：Docker Compose、Nginx、环境变量、备份、重置脚本。

## 商品图本地备份方案

- 源目录：`backend/static/products`，300 张 PNG，约 342MB。
- 按文件名首字母分 4 个 ZIP：`C` 服装、`S` 鞋靴、`B` 箱包、`A` 配饰，各 75 张；PNG 已压缩，ZIP 用存储模式，不做二次压缩。
- 备份目录：`D:\backups\graduation-project-new\2026-11-12\`，再复制一份到 `%USERPROFILE%\Backups\graduation-project-new\2026-11-12\`。
- 生成 `products-manifest.csv`（文件名、品类、字节数、SHA-256）和 `RESTORE.md`。
- 校验：ZIP 条目数、CRC、每包抽 1 张与源文件比 SHA-256、两份 ZIP 的 SHA-256 一致。
- 网盘：用户自行把 4 个 ZIP 上传到阿里云盘私有目录；上传后下载一个 ZIP 回来比对 SHA-256。

## 多窗口实施约定

用户计划每个模块开一个新窗口实现。推荐按 M0~M9 拆成约 10 个窗口，每个窗口做一个**纵向模块**（后端接口 + 前端页面 + 测试），不是按“所有后端 / 所有前端”横切。

每个窗口固定流程：

1. 开场先读：设计文档相关章节、实施计划对应模块、本交接页、`docs/progress.md`、相关现有代码。
2. 只改本模块范围内的文件；共享契约（API DTO、错误码、DB 字段、路由）不要擅自改，确需修改先更新文档。
3. 结束前跑本模块测试 + 相关 E2E；提交 git；更新 `docs/progress.md`（完成项、遗留、下一模块依赖）与 `docs/implementation-handoff.md`（当前状态、下一步）。
4. 每 2~3 个模块安排一次集成检查，不要留到答辩前。

前置条件：项目已是 git 仓库（分支 `m0-project-skeleton`），继续按每模块一提交的纪律执行；新窗口通过 `git log` 判断上一窗口改了什么。

注意：`backend/static/products` 约 342MB，不要直接提交进普通 git。用 `.gitignore` 排除商品图并单独压缩备份，或使用 Git LFS（大文件存储）；代码、文档、种子 JSON 正常提交。

## 下一步

新窗口先读：

- `docs/superpowers/specs/2026-11-11-ai-shopping-agent-design.md`（重点 §7、§8、§10.2、§11.1.3）
- `docs/superpowers/plans/2026-11-13-m0-project-skeleton.md`（已完成，作为基线参考）
- `README.md`（本地启动、测试、重置步骤）
- `docs/implementation-handoff.md`
- `docs/progress.md`（M0 记录）

然后为 M1「商品域 + 种子数据 + 商品详情」写实施计划：categories/products/product_skus/favorites 表、300 商品种子数据、商品列表/详情接口、商品详情页与收藏。

M1 只消费 `backend/static/products` 中已生成的商品图，不再做 AI 生图；接口按设计文档 §10.2 落地，至少包含 categories/products/product_skus/favorites 与商品列表/详情。
