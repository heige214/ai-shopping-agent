# 实施计划交接（2026-11-14）

## 当前状态

- 设计文档：`docs/superpowers/specs/2026-11-11-ai-shopping-agent-design.md`
  - §18 已标记「评审完成」，6 项评审全部通过。
- 页面样板（已确认，静态无功能）：
  - `docs/mockups/screens-user-part1.png`：登录、AI 导购空状态/对话、商品详情、AI 客服、知识库未命中、排队、人工会话
  - `docs/mockups/screens-user-part2.png`：购物车、结算、订单、我的
  - `docs/mockups/screens-agent.png`：客服端队列、会话工作台、知识审核
  - HTML 源文件与 `mockup.css` 在同一目录。
- 商品图片：`backend/static/products` 共 300 张（4 个一级品类 × 75），鞋靴 75 张已补齐。
- 前置状态（2026-11-14）：`git` 已初始化；M0、M1、M2、M3、M4、M4.1、M5 已完成；商品图本地备份尚未执行。
- 主项目骨架与商品域已完成：M0 认证/双 Tab/迁移/测试基线；M1 品类/商品/SKU/收藏/分类列表/商品详情/可复用商品发现组件。
- 交易域已完成（M2）：购物车、地址、订单、模拟支付/取消/确认收货、客服端已支付订单发货；库存扣减/恢复、支付幂等、超时取消、用户数据隔离与 `role ∈ {agent, admin}` 守卫均已落地。
- 知识库与商品客服已完成（M3）：913 篇知识文档 / 1813 切片（商品详情、尺码、商品 FAQ、一级品类洗护、平台政策）；商品 + 一级品类 + 平台三级范围混合检索（向量 top20 + 关键词 top20 → RRF top8）；`/api/chat/sessions` 与 SSE 消息接口；商品客服页支持流式回答、引用、反馈、每会话一次澄清、固定兜底与最小转人工 waiting 工单。无 DashScope key 时使用本地规则 + 关键词检索，知识种子 embedding 可为 NULL。
- M3 补充（2026-11-14，分支 `fix/support-size-availability`）：新增尺码库存“商品事实前置层”，`有XS的吗` 这类不带“尺码/码”的问题会先查商品库存与尺码表，再决定是否检索知识库；引用 chip 可点击，尺码引用用表格展示；`seed_knowledge.py` 支持 `--reembed` 在切换真实 embedding 模型后重建向量。真实百炼 Key 已配置，1813 条知识向量已用 `text-embedding-v3` 全量重建，后端当前使用 `qwen-plus`。
- M3 Agent（2026-11-14，同分支）：客服主链路改为 LangGraph 受控工作流 `plan → tools`，由规划模型选择 `product_facts` / `search_knowledge` / `size_stock` 工具，再流式回答；移除独立意图和可回答性模型调用，开放问题（如“这个小孩子能带吗”）不再被固定意图菜单反问。引用按问题主题收窄。M4 可直接复用 `run_support_agent` 与 `SupportPlan`。
- M4 导购（2026-11-14，分支 `m4-guide-agent`，tag `m4`）：首页改为导购聊天；`type=guide` 默认复用最近 active 会话，`new=true` 显式新建，不写问候，escalate 返回 400；槽位多轮合并；结构化过滤 + 商品向量 top30 → RRF → LLM 重排 6~8 张卡；无结果按厚薄→材质→价格放宽并澄清一次；新增 `GET /api/products/{id}/size-recommendation`；商品向量已用 `text-embedding-v3` 补齐 300/300。后端 193 pytest、前端 build、8 条 E2E 通过。
- M4.1 历史抽屉（2026-11-14，分支 `m4.1-guide-history`，tag `m4.1`）：首页顶部「历史」抽屉列出 guide 会话（标题/时间/进行中或已结束），点击切换并恢复消息与商品卡；抽屉内可显式新建会话；已结束会话输入禁用。前端 build 与 8 条 E2E 通过。
- M5 多模态与加购（2026-11-14，分支 `m5-multimodal-cart`，tag `m5`）：新增图片/语音上传与理解、两阶段 `chat_actions` 加购。图片 `POST /api/uploads/image`（jpg/png/webp ≤5MB）→ Qwen-VL 结构化描述并入 M4 槽位；语音 `POST /api/uploads/voice`（webm/mp4/wav ≤10MB）→ Paraformer 转写，前端仅回填输入框由用户确认发送。guide 支持 `content_type=image/voice`，support 仍仅文字。加购 `chat_actions`（迁移 `20261114_0005`）：`last_products` 解析“第 N 件/这个/显式商品名 + 尺码/数量”，SSE `meta → action → done`，确认/取消普通 JSON 且幂等；确认锁 action/SKU 复用 `cart_service`，库存不足/下架返回 200 + failed + 可换尺码，越权 404。后端 215 pytest、前端 build、12 条 E2E 通过。
- 本地开发端口：后端 8100（本机 Windows 保留 7997–8096，8000 不可用），前端 Vite 5175（避开本机其他项目常占用的 5173/5174），`/api` 代理指向 8100。
- 本地运行：以 `README.md` 的「本地启动」为准（Docker DB 5433、后端 8100、前端 5175、demo/demo123；客服 agent/agent123；商品与知识种子分别用 `seed_catalog` / `seed_knowledge` 导入）。

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
- 种子数据规模：300 商品、实际 1108 条 SKU（一商品一图一色、按实际尺码）、600~900 条商品 FAQ（M3 再生成）。
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

前置条件：项目已是 git 仓库（M2 完成于分支 `m2-commerce`，tag `m2`），继续按每模块一提交的纪律执行；新窗口通过 `git log` 判断上一窗口改了什么。

注意：`backend/static/products` 约 342MB，不要直接提交进普通 git。用 `.gitignore` 排除商品图并单独压缩备份，或使用 Git LFS（大文件存储）；代码、文档、种子 JSON 正常提交。

## 下一步

新窗口先读：

- `docs/superpowers/specs/2026-11-11-ai-shopping-agent-design.md`（重点 §15 M5、§9.2.1 图片/语音预处理、§10.4 上传、§10.3 `chat_actions`、§12.3 加购状态机）
- `docs/superpowers/plans/` 下 M0~M4 计划（已完成，作为基线参考）
- `README.md`（本地启动、商品/知识/商品向量种子、测试、demo/agent 账号、AI 可选配置）
- `docs/implementation-handoff.md`
- `docs/progress.md`（M0~M4 记录）

M5 已完成，交接要点：

- 上传：`app/modules/uploads/`；校验 MIME + 扩展名 + 魔数 + 大小，UUID 落盘 `backend/static/uploads/`（gitignore，不入库）。新增配置见 `.env.example`：`VISION_MODEL`、`ASR_MODEL`、`MAX_IMAGE_UPLOAD_MB`、`MAX_VOICE_UPLOAD_MB`、`UPLOAD_DIR`。
- AI 抽象：`VisionClient` / `ASRClient`（`app/ai/vision.py`、`asr.py`）；`AI_PROVIDER=fake` 使用 `FakeVisionClient`（蓝色薄款纯棉衬衫）/ `FakeASRClient`（“推荐几件衬衫”），测试与 E2E 永不访问真实百炼。无 key 图片降级文字搜索，语音返回 502 可重试。
- 消息：`append_user_message` 对 guide 放开 image/voice 并校验站内上传 URL；support 保持仅文字。图片理解写用户消息 `content.vision`；失败 `meta.degraded=true` 并提示“已按文字条件搜索”。
- 加购：`slot_state.last_products`（≤8）在 products 事件生成时写入；`GuideQuery.intent=add_to_cart` + `cart` 字段；`guide/cart.py` 负责解析/建动作，`guide/actions.py` 负责 confirm/cancel。确认/取消会同步更新 action_card 消息 content，历史恢复状态正确。
- SSE 契约：找货（含图片/语音）`meta → token* → products → done`；加购成功 `meta → action → done`（无 token/products）；需澄清时 `meta → token* → done`。确认/取消是普通 JSON，不走 SSE。
- 测试：后端 215 pytest、前端 build、12 条 E2E（含图片、假麦克风语音、加购成功/幂等/取消/库存不足失败卡）。

M4 已完成，交接要点：

- guide 会话：`POST /api/chat/sessions` 的 `type=guide` 默认复用最近 active；`new=true` 显式新建；guide 不写问候消息；guide escalate 返回 400。SSE 顺序固定 `meta → token* → products → done`。
- 槽位：`slot_state={"query": GuideQuery, "clarify_count": int}`；`merge_guide_query` 负责多轮合并、切换品类/重置词清空、档案身高体重兜底；改槽位逻辑时同步补 `tests/test_guide_slots.py`。
- 检索：`app/modules/guide/search.py` 负责品类子树、属性/价格过滤、商品向量 top30、RRF 与放宽；放宽顺序厚薄→材质→价格，颜色/品类不放宽。
- 尺码：`app/modules/guide/size.py` 与 `GET /api/products/{id}/size-recommendation`；商品详情与导购卡都展示 `recommended_size/size_reason`。
- 商品向量：`scripts/seed_product_embeddings.py`；切换 embedding 模型后必须 `--reembed`。开发库当前 300 条已有 `text-embedding-v3` 向量。
- 前端：首页 `HomeView.vue` 是导购聊天，空状态组件 `components/guide/GuideEmptyState.vue`，商品卡 `GuideProductCard.vue`，顶部「历史」抽屉支持查看/切换 guide 会话；E2E `guide.spec.ts` 覆盖聊天、历史切换与尺码卡。M4 起首页品类入口是“发送查询”按钮，`catalog.spec.ts` / `commerce.spec.ts` 已改为直达 `/category/1`，新窗口不要改回链接假设。
- 不要改 M0 认证契约、M1 商品 DTO、M2 交易契约、M3 商品客服契约与 M4 导购 SSE 顺序。

下一步进入 M6「转人工、客服端队列/工作台」：

- 复用 M3 已创建的 `support_tickets`（waiting/connected/closed）与 `chat_sessions.status=waiting_human`，补齐队列排序、客服接入、掉线回队列、工作台消息与 WebSocket。
- 不要重写 M3 support 管线、M4 guide 检索/尺码、M5 上传与 `chat_actions`；新增客服端页面沿现有 `/agent/*` 角色守卫。
- 测试/E2E 继续用 `AI_PROVIDER=fake`；真实 key 仅放 `.env`。

M1 已消费 `backend/static/products` 中 300 张商品图，不再做 AI 生图；M2 已完成交易闭环，M3 已完成商品客服，M4 已完成导购聊天，M5 已完成多模态与加购；后续模块不重新生成商品图、不改订单状态机与 M3/M4/M5 契约。
