# AI 购物导购 Agent 平台 — 设计文档

- **版本**：v0.1（第一版，待评审）
- **日期**：2026-11-11
- **项目目录**：`D:\develop\graduation-project-new`
- **定位**：本科毕业设计，个人开发，周期 3~6 个月
- **文档状态**：需求与设计已对齐，等待评审后进入实现计划

---

## 0. 需求决策记录

| # | 决策点 | 结论 |
|---|---|---|
| 1 | 项目定位 | 移动端优先的 AI 购物导购平台，含交易闭环 |
| 2 | 技术栈 | Python FastAPI + Vue 3 + TypeScript |
| 3 | 大模型服务 | 阿里云百炼 DashScope（文本/视觉/ASR/Embedding 一站配齐） |
| 4 | 商品品类 | 服饰生活 4 类：服装、鞋靴、箱包、配饰 |
| 5 | 商品规模 | 约 300 个商品，含 SKU |
| 6 | 商品图片 | AI 批量生成，统一模板，白底 |
| 7 | 图片输入 | 多模态理解（识别品类/颜色/风格后检索），不做以图搜同款 |
| 8 | 语音输入 | 后端 ASR API，前端录音上传 |
| 9 | 用户端范围 | 对话式发现（聊天空状态推荐）、AI 导购、AI 客服、收藏、购物车、订单、地址 |
| 10 | 交易范围 | 购物车 + 下单 + 模拟支付 + 模拟发货 + 确认收货；不做退款/售后 |
| 11 | 支付 | 完全模拟，不接第三方支付 |
| 12 | AI 交易能力 | AI 可加购，必须用户确认；下单仍走购物车/结算页 |
| 13 | 登录 | 聊天、收藏、交易均需登录；JWT |
| 14 | 客服端 | 同一 Vue 项目的 `/agent` 路由，按角色分流 |
| 15 | 转人工入口 | 仅商品详情页的 AI 客服；导购聊天不转人工 |
| 16 | 客服模式 | 排队 + 客服接入 + 一对一实时会话 |
| 17 | 转人工触发 | 增强策略：答不上来 + 主动 + 重复追问/不满 + 投诉售后 + 订单物流 |
| 18 | 订单类问题 | AI 一律转人工，不查个人订单数据；客服端可查 |
| 19 | AI 回答反馈 | 有帮助 / 没帮助；没帮助时弹转人工 |
| 20 | Agent Assist | 不做，作为提前完成的加分项 |
| 21 | 知识回灌 | AI 提炼 Q&A + 结构化字段建议，人工审核后入库 |
| 22 | 知识库范围 | 商品知识 + 品类共性知识 + 平台规则 |
| 23 | 整体架构 | 单体应用，FastAPI 模块分包 |
| 24 | 中间件 | 不引入 Redis、不引入 Celery；单 worker + BackgroundTasks |
| 25 | 数据库 | PostgreSQL 16 + pgvector，业务数据与向量同库 |
| 26 | 部署 | 云服务器 + 域名 + HTTPS（麦克风必需） |

---

## 1. 项目概述

### 1.1 定位

用户用自然语言描述购物需求（可附带图片、语音），系统完成：

1. 意图解析与槽位提取
2. 商品检索与推荐（结构化过滤 + 向量召回 + LLM 重排）
3. 尺码推荐
4. 商品详情页的 AI 客服问答（RAG）
5. 答不上来时转人工
6. 人工会话结束后，AI 提炼知识，人工审核后回灌知识库

核心不是"一个带聊天框的电商网站"，而是**带 Human-in-the-loop 知识进化闭环的导购 Agent**。

### 1.2 论文主线与创新点

**主线**：面向电商导购的 RAG Agent 与 Human-in-the-loop 知识进化闭环。

**创新点**：

1. **Schema 驱动的多品类商品建模与混合检索**：属性 schema 配置化，新增品类不改检索代码；结构化过滤 + 向量召回 + RRF 融合 + LLM 重排。
2. **分级转人工策略**：不是简单"检索不到就转"，而是可回答性判断 + 多信号触发 + 转人工前一次澄清 + 上下文交接。
3. **双通道知识回灌**：人工会话同时沉淀文本知识（FAQ chunk）和结构化字段（尺码建议、材质说明），经人工审核后生效，并保留审计轨迹。
4. **可复现的评测体系**：检索、回答忠实度、转人工准确率、尺码准确率、AI 解决率与满意度，含消融实验。

### 1.3 角色

| 角色 | 权限 |
|---|---|
| 普通用户 | 对话式发现、AI 导购、商品客服、收藏、购物车、下单、订单、地址 |
| 客服（agent） | 接待转人工会话、查看用户/订单上下文、模拟发货、审核知识 |
| 管理员（admin） | 首版与客服合并；保留种子数据与知识管理能力 |

---

## 2. 目标与非目标

### 2.1 目标

- 移动端 H5，两个导航：AI 找货（默认）、我的；发现入口放在聊天空状态
- 自然语言找货 + 主动澄清 + 尺码推荐
- 商品详情页 AI 客服 + 转人工 + 客服工作台
- 交易闭环：购物车、地址、订单、模拟支付、模拟发货、确认收货
- 知识闭环：会话提炼 → 人工审核 → 入库 → 审计
- 多模态输入：图片理解、语音转写
- 可部署、可演示、可评测、论文有实验数据

### 2.2 非目标

- 真实支付、物流、退款、售后
- 全局悬浮客服、电话语音客服
- 多租户、多仓库存、优惠券、商品评价
- 全自主 ReAct Agent 循环
- Agent Assist（客服端 AI 辅助回复）
- 原生 App、微信小程序、PWA 打包（客户端只做移动端 H5）
- 高并发/多实例部署（单 worker，扩展路径见 5.3）

---

## 3. 核心场景

### 3.1 导购场景

> 用户："我想要一件薄衬衫，蓝色，我的身高 172，体重 75kg"

1. 解析出品类=服装/衬衫、颜色=蓝色、厚薄=薄款、身高体重
2. 结构化过滤 + 向量召回 + 重排，返回 5 件商品
3. 每件商品按尺码表给出推荐尺码（L）与依据
4. 用户点"加入购物车" → 确认卡片 → 确认后写入购物车
5. 用户去购物车结算

### 3.2 商品客服场景

> 用户在商品详情页问："这件衬衫会起球吗？"

1. 意图识别为 `product_qa`
2. 检索当前商品 + 品类 + 平台知识
3. 可回答性判断通过 → 流式回答 + 引用来源
4. 若判断不通过 → 先澄清一次；仍无法回答 → "知识库暂未检索到有效信息" + 转人工
5. 用户点转人工 → 排队 → 客服接入 → 实时对话 → 结束 → 评分
6. 后台提炼 Q&A 与字段建议 → 客服审核 → 入库

### 3.3 交易场景

> 商品详情选颜色/尺码 → 加入购物车 → 结算 → 创建订单（锁库存）→ 模拟支付 → 客服端模拟发货 → 用户确认收货。

---

## 4. 技术选型

| 层 | 选型 | 说明 |
|---|---|---|
| 前端 | Vue 3 + Vite + Pinia + Vue Router + Vant 4 + TypeScript | 移动端 H5；`/agent` 客服端同项目 |
| 后端 | Python 3.11 + FastAPI + Pydantic v2 | 异步 I/O，适合 LLM/流式场景 |
| ORM/迁移 | SQLAlchemy 2.0 + Alembic | 类型化模型与版本化迁移 |
| 数据库 | PostgreSQL 16 + pgvector | 业务数据 + 向量同库，减少中间件 |
| 文本模型 | DashScope `qwen-plus` | 意图解析、重排、回答、提炼；可切 qwen-max |
| 视觉模型 | DashScope `qwen3-vl-flash` | 图片理解；更便宜、OCR/grounding 更强，必要时可切 `qwen3-vl-plus` |
| 语音识别 | DashScope `paraformer-v2` | 后端 ASR |
| Embedding | DashScope `text-embedding-v4`，1024 维 | 商品向量 + 知识 chunk 向量；与 v3 同价，支持 2048 维，本项目固定 1024 维 |
| AI 流式 | SSE | 单向上行请求 + 流式下行 |
| 人工聊天 | WebSocket | 双向实时 |
| 部署 | Docker Compose + Nginx + Certbot | 单机部署，HTTPS |
| 缓存/队列 | 无 Redis、无 Celery | 单 worker；Postgres 存状态；BackgroundTasks 跑提炼 |
| 认证 | JWT + bcrypt | 角色：user / agent / admin |
| 前端测试 | Playwright | 关键链路 E2E |
| 后端测试 | pytest + httpx | 单元 + 集成；AI 客户端可 mock |

**Vue 使用 TypeScript**：代码主要由 AI 生成，类型能提前暴露接口不一致；如后期觉得负担大，可退化为 JavaScript，不影响架构。

**模型版本说明（2026-11 核实）**：视觉使用 `qwen3-vl-flash`（Qwen3-VL 系列，2025-09 发布；轻量、低成本，适合商品图与聊天图片输入，必要时可切 `qwen3-vl-plus`）。Embedding 使用 `text-embedding-v4`（与 v3 同价，支持 1024~2048 维；本项目固定 1024 维，pgvector 列不变）。ASR 保留 `paraformer-v2`，官方仍将其列为性价比路线，聊天短语音足够；方言/噪声场景可切 `qwen3-asr-flash`。模型名与价格以百炼控制台为准。

---

## 5. 总体架构

### 5.1 架构图

```text
┌──────────────────────────┐      ┌──────────────────────────┐
│  Vue 3 H5 用户端          │      │  Vue 3 客服端 /agent      │
│  AI 聊天 / 我的            │      │  队列 / 会话 / 订单 / 知识 │
└────────────┬─────────────┘      └────────────┬─────────────┘
             │ HTTPS                            │ HTTPS
             └──────────────┬───────────────────┘
                            ▼
                         Nginx
              ┌─────────────┼──────────────┐
              ▼             ▼              ▼
         静态资源        FastAPI        /static /uploads
         (Vue dist)     (1 worker)
                            │
        ┌───────────────────┼────────────────────┐
        ▼                   ▼                    ▼
  业务模块               AI 编排层            实时层
  auth/catalog          chat/retrieval       SSE / WebSocket
  commerce/knowledge    support/knowledge    in-process manager
  support
        │                   │
        └──────────┬────────┘
                   ▼
        PostgreSQL 16 + pgvector
                   │
                   ▼
        阿里云百炼 DashScope
        Qwen / Qwen-VL / Paraformer / Embedding
```

### 5.2 请求链路

| 场景 | 协议 | 说明 |
|---|---|---|
| 普通业务 | REST/JSON | 商品、收藏、购物车、订单、地址 |
| AI 聊天 | POST + SSE | 请求一次，响应流式事件 |
| 人工聊天 | WebSocket | 用户与客服双向实时 |
| 后台任务 | BackgroundTasks | 知识提炼、商品向量重建 |
| 文件 | multipart | 图片/语音上传 |

### 5.3 单机边界与扩展路径

- 后端固定 **1 个 uvicorn worker**，WebSocket 连接管理在进程内，会话状态存 Postgres。
- 当前规模（300 商品、几十并发）单 worker 足够。
- 扩展到多 worker / 多实例时：
  1. `realtime` 层实现 Redis Pub/Sub 广播；
  2. 连接注册表迁移到 Redis；
  3. 后台任务迁移到 Celery + Redis。
- 代码层面把 `realtime` 定义为接口（publish/subscribe），业务代码不直接依赖进程内字典。

---

## 6. 工程结构

```text
graduation-project/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/                 # 配置、安全、日志、异常、依赖注入
│   │   ├── db/                   # engine、session、Base
│   │   ├── modules/
│   │   │   ├── auth/             # 用户、登录、角色
│   │   │   ├── catalog/          # 品类、商品、SKU、收藏
│   │   │   ├── commerce/         # 购物车、地址、订单、模拟支付/发货
│   │   │   ├── chat/             # AI 会话、消息、编排器、动作
│   │   │   ├── retrieval/        # 结构化过滤、向量召回、RRF、重排
│   │   │   ├── knowledge/        # 文档、chunk、提炼、审核、入库
│   │   │   ├── support/          # 工单、排队、客服端接口
│   │   │   └── realtime/         # WebSocket 连接管理接口
│   │   ├── ai/                   # LLM/VL/ASR/Embedding 客户端与 prompt
│   │   └── workers/              # BackgroundTasks：提炼、向量重建
│   ├── alembic/
│   ├── scripts/                  # 种子数据、生图、知识构建、评测
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── fixtures/
├── frontend/
│   ├── src/
│   │   ├── views/user/           # home / chat / product / cart / checkout / orders / me / login
│   │   ├── views/agent/          # queue / chat / orders / knowledge
│   │   ├── components/
│   │   ├── stores/
│   │   ├── api/
│   │   ├── router/
│   │   └── types/
│   └── tests/
│       └── e2e/
├── deploy/                       # docker-compose.yml、nginx.conf、certbot
├── docs/
│   ├── superpowers/specs/        # 本设计文档
│   ├── evaluation/               # 评测集与结果
│   └── thesis/                   # 论文素材
└── README.md
```

---

## 7. 数据模型

### 7.1 ER 关系概览

```text
users 1─N addresses
users 1─N favorites N─1 products
users 1─N cart_items N─1 product_skus N─1 products
users 1─N orders 1─N order_items N─1 product_skus
categories 1─N products 1─N product_skus

users 1─N chat_sessions 1─N chat_messages
chat_sessions 1─N chat_actions
chat_sessions 1─1 support_tickets

support_tickets 1─N knowledge_candidates
knowledge_documents 1─N knowledge_chunks
products 1─N knowledge_documents（scope=product）
categories 1─N knowledge_documents（scope=category）
products 1─N knowledge_candidates
products 1─N product_field_history
```

### 7.2 表定义

> 所有表默认包含 `created_at TIMESTAMPTZ`；需要更新的表包含 `updated_at TIMESTAMPTZ`。

#### 7.2.1 用户域

**users**

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BIGSERIAL PK | |
| username | VARCHAR(50) UNIQUE NOT NULL | 登录名 |
| password_hash | VARCHAR(255) NOT NULL | bcrypt |
| nickname | VARCHAR(50) | 昵称 |
| avatar_url | VARCHAR(500) | 头像 |
| role | VARCHAR(20) NOT NULL | user / agent / admin |
| height_cm | SMALLINT | 身高，尺码推荐用 |
| weight_kg | SMALLINT | 体重，尺码推荐用 |
| usual_size | VARCHAR(10) | 常穿尺码，可选 |

**addresses**

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BIGSERIAL PK | |
| user_id | BIGINT FK users | |
| receiver_name | VARCHAR(50) | 收货人 |
| phone | VARCHAR(20) | 手机号 |
| province / city / district | VARCHAR(50) | 省市区 |
| detail | VARCHAR(255) | 详细地址 |
| is_default | BOOLEAN DEFAULT false | 默认地址 |

#### 7.2.2 商品域

**categories**

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BIGSERIAL PK | |
| parent_id | BIGINT NULL FK categories | 一级品类为 NULL |
| name | VARCHAR(50) NOT NULL | 品类名 |
| slug | VARCHAR(50) UNIQUE | 英文标识 |
| level | SMALLINT | 1=一级，2=叶子 |
| attribute_schema | JSONB NOT NULL DEFAULT '{}' | 属性定义 |
| size_chart_template | JSONB NULL | 尺码表模板（服装/鞋靴） |
| sort_order | INT DEFAULT 0 | 推荐排序（热度） |

**products**

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BIGSERIAL PK | |
| category_id | BIGINT FK categories | 叶子品类 |
| title | VARCHAR(200) NOT NULL | 标题 |
| description | TEXT | 描述 |
| brand | VARCHAR(100) | 品牌 |
| price | NUMERIC(10,2) NOT NULL | 基础价 |
| original_price | NUMERIC(10,2) | 划线价 |
| main_image | VARCHAR(500) | 主图 |
| images | JSONB DEFAULT '[]' | 图片数组 |
| attributes | JSONB NOT NULL DEFAULT '{}' | 差异属性（冗余，供检索/展示） |
| size_chart | JSONB NULL | 商品级尺码表，覆盖品类模板 |
| status | VARCHAR(20) DEFAULT 'on_sale' | on_sale / off_shelf |
| sales_count | INT DEFAULT 0 | 热度排序 |
| embedding | vector(1024) NULL | 商品语义向量 |

**product_skus**

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BIGSERIAL PK | |
| product_id | BIGINT FK products | |
| color | VARCHAR(30) | 颜色 |
| size | VARCHAR(20) | 尺码 |
| stock | INT NOT NULL DEFAULT 0 | 库存 |
| price_override | NUMERIC(10,2) NULL | 可选价格覆盖；下单价 = price_override ?? products.price |
| sku_code | VARCHAR(50) UNIQUE | SKU 编码 |
| status | VARCHAR(20) DEFAULT 'active' | active / inactive |

约束：`UNIQUE(product_id, color, size)`。

**favorites**

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BIGSERIAL PK | |
| user_id | BIGINT FK users | |
| product_id | BIGINT FK products | |

约束：`UNIQUE(user_id, product_id)`。

#### 7.2.3 交易域

**cart_items**

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BIGSERIAL PK | |
| user_id | BIGINT FK users | |
| sku_id | BIGINT FK product_skus | |
| quantity | INT NOT NULL CHECK (quantity > 0) | |
| selected | BOOLEAN DEFAULT true | 结算勾选 |

约束：`UNIQUE(user_id, sku_id)`。

**orders**

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BIGSERIAL PK | |
| order_no | VARCHAR(32) UNIQUE NOT NULL | 订单号 |
| user_id | BIGINT FK users | |
| address_snapshot | JSONB NOT NULL | 下单时地址快照 |
| total_amount | NUMERIC(10,2) NOT NULL | 总额 |
| status | VARCHAR(20) NOT NULL | 见 12.1 |
| payment_method | VARCHAR(20) DEFAULT 'simulated' | 模拟支付 |
| payment_no | VARCHAR(50) NULL | 假流水号 |
| paid_at / shipped_at / completed_at / cancelled_at | TIMESTAMPTZ NULL | 状态时间 |
| expires_at | TIMESTAMPTZ NOT NULL | 待支付超时时间（创建 + 15 分钟） |

**order_items**

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BIGSERIAL PK | |
| order_id | BIGINT FK orders | |
| sku_id | BIGINT FK product_skus | |
| product_id | BIGINT FK products | |
| title_snapshot | VARCHAR(200) | 下单时标题 |
| image_snapshot | VARCHAR(500) | 下单时图片 |
| price_snapshot | NUMERIC(10,2) | 下单时单价 |
| color_snapshot | VARCHAR(30) | 颜色快照 |
| size_snapshot | VARCHAR(20) | 尺码快照 |
| quantity | INT NOT NULL | 数量 |

#### 7.2.4 会话与客服域

**chat_sessions**

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BIGSERIAL PK | |
| user_id | BIGINT FK users | |
| type | VARCHAR(20) NOT NULL | guide / support |
| product_id | BIGINT NULL FK products | support 会话绑定商品 |
| title | VARCHAR(200) | 会话标题（首条消息摘要） |
| status | VARCHAR(20) NOT NULL | active / waiting_human / human / closed |
| slot_state | JSONB DEFAULT '{}' | 槽位状态、澄清次数、重复次数、上次推荐商品 |
| summary | TEXT | 会话摘要（长会话压缩用） |

**chat_messages**

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BIGSERIAL PK | |
| session_id | BIGINT FK chat_sessions | |
| sender_type | VARCHAR(20) NOT NULL | user / ai / agent / system |
| sender_id | BIGINT NULL | agent 消息记录客服 ID |
| content_type | VARCHAR(20) NOT NULL | text / image / voice / product_cards / action_card / system_event |
| content | JSONB NOT NULL | 见 10.3 |
| meta | JSONB DEFAULT '{}' | 检索候选、分数、过滤器、耗时、反馈 |

**chat_actions**

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BIGSERIAL PK | |
| session_id | BIGINT FK chat_sessions | |
| message_id | BIGINT FK chat_messages | 对应的 action_card 消息 |
| action_type | VARCHAR(30) NOT NULL | add_to_cart |
| payload | JSONB NOT NULL | sku_id、product_id、quantity 等 |
| status | VARCHAR(20) NOT NULL | pending / confirmed / cancelled / executed / failed |
| result | JSONB DEFAULT '{}' | 执行结果或错误 |
| executed_at | TIMESTAMPTZ NULL | |

**support_tickets**

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BIGSERIAL PK | |
| session_id | BIGINT FK chat_sessions | |
| user_id | BIGINT FK users | |
| product_id | BIGINT NULL FK products | |
| status | VARCHAR(20) NOT NULL | waiting / connected / closed |
| assigned_agent_id | BIGINT NULL FK users | |
| context_summary | TEXT | 转人工时生成的诉求摘要 |
| extraction_status | VARCHAR(20) DEFAULT 'pending' | pending / running / done / failed |
| close_reason | VARCHAR(50) NULL | 用户结束/客服结束/超时 |
| rating | SMALLINT NULL | 1~5 星 |
| rating_comment | VARCHAR(500) NULL | |
| connected_at / closed_at | TIMESTAMPTZ NULL | |

#### 7.2.5 知识域

**knowledge_documents**

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BIGSERIAL PK | |
| scope | VARCHAR(20) NOT NULL | product / category / platform |
| product_id | BIGINT NULL FK products | scope=product 时必填 |
| category_id | BIGINT NULL FK categories | scope=category 时必填 |
| doc_type | VARCHAR(30) NOT NULL | detail / faq / size / care / policy |
| title | VARCHAR(200) | |
| source | VARCHAR(30) NOT NULL | seed / session_extraction / manual |
| status | VARCHAR(20) DEFAULT 'active' | active / archived |

**knowledge_chunks**

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BIGSERIAL PK | |
| document_id | BIGINT FK knowledge_documents | |
| product_id | BIGINT NULL | 冗余，便于按商品过滤 |
| category_id | BIGINT NULL | 冗余，便于按品类过滤 |
| content | TEXT NOT NULL | 切片正文 |
| search_text | TEXT | jieba 分词后的文本，供全文检索 |
| embedding | vector(1024) | |
| meta | JSONB DEFAULT '{}' | question、section、doc_type、candidate_id |

**knowledge_candidates**

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BIGSERIAL PK | |
| ticket_id | BIGINT FK support_tickets | |
| product_id | BIGINT FK products | |
| type | VARCHAR(20) NOT NULL | faq / field |
| payload | JSONB NOT NULL | FAQ 的 question/answer 或字段的 field/value |
| confidence | NUMERIC(4,3) | 0~1 |
| status | VARCHAR(20) NOT NULL | pending / approved / rejected |
| duplicate_of | BIGINT NULL FK knowledge_chunks | 命中已有知识时记录 |
| review_note | VARCHAR(500) NULL | 审核备注 |
| reviewed_by | BIGINT NULL FK users | |
| reviewed_at | TIMESTAMPTZ NULL | |

**product_field_history**

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BIGSERIAL PK | |
| product_id | BIGINT FK products | |
| field | VARCHAR(50) NOT NULL | 如 fit_notes |
| old_value | JSONB NULL | |
| new_value | JSONB | |
| candidate_id | BIGINT NULL FK knowledge_candidates | 来源可追溯 |

### 7.3 索引与向量

| 对象 | 索引 |
|---|---|
| `products.embedding` | HNSW（`vector_cosine_ops`） |
| `knowledge_chunks.embedding` | HNSW（`vector_cosine_ops`） |
| `products.attributes` | GIN |
| `knowledge_chunks.search_text` | GIN（`to_tsvector('simple', search_text)`） |
| `products.category_id`、`product_skus.product_id` | B-tree |
| `chat_messages(session_id, created_at)` | B-tree |
| `support_tickets(status, created_at)` | B-tree |
| `knowledge_candidates(status, product_id)` | B-tree |
| `orders(user_id, created_at)`、`orders.status` | B-tree |
| `cart_items.user_id` | B-tree |

### 7.4 关键设计决定

1. **商品属性用 JSONB + 品类 schema 驱动**。公共属性放在一级品类，叶子品类扩展；后端沿树合并。新增品类只配 schema + 造数据，检索代码不动。
2. **商品/SKU 分离**。商品负责展示和检索，SKU 负责颜色/尺码/库存/价格；购物车与订单必须落到 SKU。
3. **订单全部存快照**。地址、标题、图片、价格、颜色、尺码都存快照，商品改价不影响历史订单。
4. **知识库分三层 scope**：product（商品专属）、category（品类共性）、platform（平台规则）。检索时按商品 → 品类祖先 → 平台合并，减少重复知识。
5. **`knowledge_candidates` 是知识闭环的闸门**。AI 提炼不直接写库，必须先审核；通过后写文档/chunk 或更新商品字段。
6. **`product_field_history` 保留结构化回填的审计轨迹**，论文可分析哪些字段最常被补充。
7. **阅读/写分离的向量字段**：商品向量用于找货，知识 chunk 向量用于问货，互不干扰。

---

## 8. 商品数据与知识库建设

### 8.1 品类与属性 Schema

一级品类与叶子划分（共 34 个叶子）：

```text
服装（10）
  ├─ 衬衫
  ├─ T恤
  ├─ 裤装
  ├─ 连衣裙
  ├─ 外套
  ├─ 针织衫
  ├─ 卫衣
  ├─ 半身裙
  ├─ 西装
  └─ 风衣
鞋靴（8）
  ├─ 运动鞋
  ├─ 休闲鞋
  ├─ 皮鞋
  ├─ 靴子
  ├─ 帆布鞋
  ├─ 凉鞋
  ├─ 拖鞋
  └─ 高跟鞋
箱包（8）
  ├─ 双肩包
  ├─ 手提包
  ├─ 单肩包
  ├─ 斜挎包
  ├─ 钱包
  ├─ 行李箱
  ├─ 托特包
  └─ 腰包
配饰（8）
  ├─ 帽子
  ├─ 围巾
  ├─ 腰带
  ├─ 袜子
  ├─ 手套
  ├─ 墨镜
  ├─ 项链
  └─ 手表
```

**一级品类公共属性（服装）**：

```json
{
  "attributes": [
    {"key": "color", "label": "颜色", "type": "enum", "options": ["黑色", "白色", "蓝色", "灰色", "卡其"], "filterable": true},
    {"key": "material", "label": "材质", "type": "enum", "options": ["棉", "麻", "真丝", "聚酯纤维", "羊毛"], "filterable": true},
    {"key": "thickness", "label": "厚薄", "type": "enum", "options": ["薄款", "常规", "加厚"], "filterable": true},
    {"key": "fit", "label": "版型", "type": "enum", "options": ["修身", "常规", "宽松"], "filterable": true},
    {"key": "size", "label": "尺码", "type": "enum", "options": ["S", "M", "L", "XL", "XXL"], "filterable": true},
    {"key": "gender", "label": "适用性别", "type": "enum", "options": ["男", "女", "中性"], "filterable": true},
    {"key": "season", "label": "季节", "type": "enum", "options": ["春", "夏", "秋", "冬"], "filterable": true}
  ]
}
```

**叶子扩展示例（衬衫）**：

```json
{
  "attributes": [
    {"key": "collar_type", "label": "领型", "type": "enum", "options": ["标准领", "立领", "古巴领"], "filterable": true},
    {"key": "sleeve_length", "label": "袖长", "type": "enum", "options": ["短袖", "长袖"], "filterable": true},
    {"key": "pattern", "label": "图案", "type": "enum", "options": ["纯色", "条纹", "格纹"], "filterable": true}
  ]
}
```

后端合并规则：从叶子到根依次合并 `attributes`，同 key 以叶子为准。

### 8.2 商品与 SKU 数据

- 总量约 300 个商品，4 个一级品类各约 75 个。
- 每个商品 1~3 个颜色、4~5 个尺码，生成约 3000~5000 条 SKU。
- 商品属性必须与图片严格一致（颜色、品类、材质），这是检索演示可信度的基础。
- 种子数据用 JSON 文件维护，脚本导入；SKU 由脚本按商品配置批量生成，库存随机 0~50。
- 每个商品配一份 `size_chart`；服装用身高/体重/胸围，鞋靴用脚长/欧码。

### 8.3 商品图片生成

- 工具：火山方舟 Seedream（`doubao-seedream-5-0-flash`），批量脚本位于 `tools/image-batch`。
- 统一模板：固定提示词（品类、颜色/色值、材质、版型、关键特征、构图、白底/浅灰底），无模特、无文字/logo。
- 输出 1024×1024 PNG，存 `backend/static/products/{id}_{color}.png`；一个商品一张主图。
- 批量生成后抽查，画崩的单独重生成；断点续跑靠「跳过已存在文件」。
- 失败兜底：纯色占位图 + 商品名，保证页面不空。

### 8.4 知识库内容清单

| 层级 | 文档类型 | 内容 | 数量估算 |
|---|---|---|---|
| product | detail | 商品详情：概述、材质、版型、适用场景 | 300 份，每份 2~3 chunk |
| product | size | 尺码指南：尺码表 + 测量说明 | 300 份，每份 1 chunk |
| product | faq | 商品常见问题（材质、厚薄、洗护、色差等） | 每商品 2~3 条，约 600~900 chunk |
| category | care | 材质洗护共性知识 | 4 份（一级品类，叶子继承） |
| category | faq | 品类共性 FAQ（如"棉质怎么洗"） | 一级品类各 5~8 条，共 20~32 条 |
| platform | policy | 发货、退换、支付、发票、优惠券、客服时间 | 8~10 份 |

**层级约定**：category 层知识只写在一级品类（4 个），34 个叶子继承，不单独编写；检索时按叶子 → 一级 → 平台合并。

**生成方式**：

- 商品详情文档：由结构化属性 + 模板生成全部 300 份；仅重点商品（20~30 个）由 LLM 润色，不允许新增未提供的参数。
- 尺码指南：直接由 `size_chart` 模板生成，规则化。
- 洗护说明：按材质映射到预置文案，避免 LLM 编造。
- 商品 FAQ：全模板生成（600~900 条），问题来自固定题库，答案由属性 + 材质洗护片段填充，多套句式轮换；不逐条 LLM 润色，只抽查。
- 品类 FAQ：4 个一级品类 × 5~8 条，由 LLM 起草，100% 人工审核通过后入库，为知识库补充自然语言表达。
- 平台政策：人工编写，固定版本。
- 种子知识审核：导出 CSV 审核表（层级/问题/答案/来源/状态），品类 FAQ 全审，商品 FAQ 抽查；导入脚本只导入 approved（已通过）行。

**去重**：新增知识前用 embedding 与已有 chunk 比对，余弦相似度 > 0.92 视为重复，不重复入库。

### 8.5 切片与检索范围

- 切片长度 200~500 字；FAQ 一条一个 chunk；详情按小节切。
- 每个 chunk 存 `product_id`、`category_id`、`meta.question`、`meta.section`，方便过滤与引用。
- `search_text` 用 jieba 分词后写入，配合 GIN 做关键词召回。
- 商品客服检索范围：当前商品 chunk + 品类祖先 chunk + 平台 chunk。
- 导购检索不使用知识 chunk，使用商品结构化字段 + 商品向量。

---

## 9. AI 链路

### 9.1 总览

同一个编排器，两条管线：

```text
导购管线：
文本/图片/语音 → 预处理 → 意图+槽位 → 澄清? → 检索(结构化+向量) → 重排 → 尺码 → 回复+商品卡 → 加购(确认)

客服管线：
输入 → 意图路由 → 混合检索(商品/品类/平台) → 可回答性判断
   ├─ 能答 → 流式回答 + 引用
   └─ 不能答 → 澄清一次 → 仍不能答 → 固定话术 + 转人工
                                                ↓
                                 排队 → 客服接入 → 人工会话 → 结束 → 评分
                                                ↓
                                 AI 提炼 → 人工审核 → 入库
```

### 9.2 导购管线

#### 9.2.1 输入预处理

| 输入 | 处理 |
|---|---|
| 文本 | 直接进入解析 |
| 语音 | 前端 MediaRecorder 录音 → 上传 → Paraformer 转写 → 转写文本回填输入框，用户可编辑后发送 |
| 图片 | 上传 → Qwen-VL 输出结构化描述 → 与文本合并 |

图片理解输出示例：

```json
{
  "category_path": ["服装", "衬衫"],
  "attributes": {
    "color": ["蓝色"],
    "material": ["棉"],
    "thickness": ["薄款"],
    "pattern": ["纯色"]
  },
  "description": "一件蓝色长袖薄款纯色衬衫",
  "confidence": 0.86
}
```

#### 9.2.2 意图与槽位解析

注入当前品类 schema，LLM 输出 JSON：

```json
{
  "intent": "search",
  "query": {
    "semantic": "适合夏天穿的薄衬衫",
    "category_path": ["服装", "衬衫"],
    "filters": {"color": ["蓝色"], "thickness": ["薄款"]},
    "price": {"min": null, "max": 300},
    "size_profile": {"height_cm": 172, "weight_kg": 75}
  },
  "missing_slots": [],
  "clarify": null
}
```

- `intent`：`search / refine / add_to_cart / ask_product / chitchat / other`
- 多轮修改合并 `slot_state`，不重建整个 query。
- 身高体重优先取用户档案，其次取本轮/历史消息，最后 null。

#### 9.2.3 澄清策略

触发条件：

- 品类缺失且语义检索置信度低
- 结果过多（>20）且没有任何过滤条件
- 条件互相矛盾（如价格区间为空）

规则：

- 每轮最多问 1~2 个问题，带快捷选项
- 用户说"随便看看/都可以"时不追问，返回热门商品
- 澄清次数记录在 `slot_state.clarify_count`，避免无限追问

#### 9.2.4 检索与重排

```text
结构化候选：category 子树 + JSONB 属性过滤 + 价格区间 + on_sale
语义候选：products.embedding 余弦召回 top 30
融合：RRF（k=60）取 top 30
重排：LLM 选出 6~8 个最匹配商品，输出 product_id + reason
无结果：逐级放宽（厚薄 → 材质 → 价格），在回复中说明放宽项
```

- 结构化过滤使用递归 CTE 取品类子树。
- JSONB 过滤用 `@>` 做数组/字符串包含；数值属性用 JSONB path 查询。
- RRF 公式：`score = Σ 1 / (k + rank_i)`。
- 重排 prompt 只给候选的标题、品牌、关键属性、价格、描述摘要，不整段塞 description。

#### 9.2.5 尺码推荐

规则：

1. 身高、体重同时命中某尺码区间 → 推荐该尺码
2. 命中多行 → 取到区间中心归一化距离最小的一行；并列时取较大尺码
3. 都不命中 → 取距离最近的一行，附"建议试穿"
4. 缺少身高/体重 → 不推荐，提示补充或去商品详情看尺码表

LLM 只负责把结果组织成自然语言，不参与判断。每个商品卡片返回 `recommended_size` 和 `size_reason`。

#### 9.2.6 回复生成

- 一段简短总结：为什么推荐、放宽了什么、尺码建议
- 商品卡片：图片、标题、价格、关键属性、推荐尺码、推荐理由、[查看详情] [加入购物车]
- 流式输出总结文本；卡片作为单独 SSE 事件

#### 9.2.7 加购动作（两阶段）

```text
用户："把第二件加到购物车"
  → 从上下文解析商品；尺码缺失时用推荐尺码，仍无法确定则反问
  → 写 chat_actions（pending）
  → 返回 action_card："确认将 [商品] 蓝色 L 码 ×1 加入购物车？[确认][取消]"
  → 用户确认
  → 校验库存、写 cart_items、动作置 executed
  → 返回结果卡片 + [去购物车]
```

- 确认接口幂等：动作状态不是 pending 时直接返回当前状态，不重复加购。
- 库存不足返回失败卡片，并推荐同款其他 SKU 或相似商品。

### 9.3 商品客服管线

#### 9.3.1 意图路由

LLM 输出：

```json
{
  "intent": "product_qa | size_qa | policy_qa | order_qa | complaint | chitchat | unknown",
  "entities": {"question_topic": "起球", "order_no": null}
}
```

路由规则：

| intent | 处理 |
|---|---|
| product_qa / size_qa / policy_qa | 进入 RAG 检索与回答 |
| order_qa | 不查个人订单，直接转人工 |
| complaint | 直接转人工，附带摘要 |
| chitchat | 简短回应并引导回商品问题 |
| unknown | 尝试澄清一次，仍无法识别则转人工 |

#### 9.3.2 检索

- 范围：当前商品 chunk + 品类祖先 chunk + 平台 chunk
- 混合检索：向量 top 20 + 关键词 top 20 → RRF → top 8
- 上下文同时注入商品事实表（属性、尺码表、价格、库存），即使 chunk 没命中，基础属性问题也能答

#### 9.3.3 可回答性判断

独立 LLM 调用，输入问题 + 商品事实表 + top chunks，输出：

```json
{
  "can_answer": true,
  "confidence": 0.87,
  "partial": false,
  "missing": null
}
```

判定规则：

- 无 chunk 且相似度低于阈值 0.35 → 直接判不可答，不调用 LLM
- `can_answer=false` 或 `confidence < 0.6` → 走澄清/转人工
- `partial=true` → 回答已知部分，剩余部分建议转人工

#### 9.3.4 回答生成

- 温度 0.2，严格 system prompt：只依据商品事实表和检索 chunk，不编造
- 流式输出，末尾附引用来源
- 引用格式：`[商品详情]`、`[尺码指南]`、`[平台规则]`
- 回答长度控制在 200 字以内，超长分段

#### 9.3.5 澄清与兜底

- 不可答时先澄清一次（"您是想问尺码、材质还是洗护？"），记录 `clarify_count`
- 仍不可答 → 固定话术："知识库暂未检索到有效信息，建议转人工客服进一步确认。" + [转人工] 按钮
- 用户可随时主动点转人工

### 9.4 转人工策略

#### 9.4.1 触发条件（增强）

1. AI 答不上来（可回答性判断失败，且已澄清一次）
2. 用户主动点"转人工"
3. 同一问题重复追问 ≥ 2 次，或用户明确表达不满（每轮计算与上一轮用户问题的语义相似度，`repeat_count` 存 `slot_state`）
4. 意图为投诉、售后、退款
5. 意图为订单/物流查询
6. 用户点击 AI 回答的"没帮助"

#### 9.4.2 上下文交接

创建工单时生成 `context_summary`，包含：

- 用户原始问题
- AI 已尝试的回答与未解决点
- 商品信息（标题、价格、关键属性）
- 用户画像（身高、体重、常穿尺码）
- 重复次数 / 情绪标记

客服接入后首先看到摘要，而不是让用户重述。

#### 9.4.3 排队与接入

```text
转人工 → support_tickets(waiting) → WebSocket 通知在线客服
      → 用户看到排队位置
      → 客服 accept（乐观锁，防止多人抢单）
      → support_tickets(connected) + chat_session(human)
      → 双方 WebSocket 实时消息
      → 客服 close → 工单 closed → 会话 closed → 触发提炼
      → 用户评分（1~5 星）
```

- 队列位置 = 比当前工单更早的 waiting 工单数 + 1。
- 客服接入使用 `UPDATE ... WHERE status='waiting'` 的原子更新，受影响行数为 0 说明已被抢。
- 首版不做客服在线状态、超时重分配、技能路由。

### 9.5 知识提炼与审核

#### 9.5.1 触发

- 工单关闭后，BackgroundTasks 异步执行
- 失败或进程重启丢失时，客服端可手动"重新提炼"（`POST /api/agent/tickets/{id}/extract`）
- 工单通过 `support_tickets.extraction_status`（pending/running/done/failed）记录状态

#### 9.5.2 提炼输出

```json
{
  "faq_candidates": [
    {
      "question": "175cm 70kg 穿什么码？",
      "answer": "建议 L 码，肩宽和胸围都在 L 码区间。",
      "confidence": 0.92,
      "evidence_message_ids": [12, 15, 18]
    }
  ],
  "field_suggestions": [
    {
      "field": "fit_notes",
      "value": "版型偏大一码，建议选小一码",
      "confidence": 0.84,
      "evidence_message_ids": [13, 17]
    }
  ]
}
```

字段建议限定在白名单：`fit_notes`、`material_notes`、`care_notes`、`quality_notes`，避免模型随意加字段。

#### 9.5.3 去重与审核

- 候选 FAQ 先 embedding，与已有 chunk 比对；相似度 > 0.92 时把已有 chunk 写入 `duplicate_of`，默认不展示或折叠
- 写入 `knowledge_candidates`（pending）
- 客服在 `/agent/knowledge` 逐条查看：证据摘录、置信度、重复标记
- 可编辑、通过、拒绝
- 通过后：
  - FAQ → 创建 `knowledge_document(scope=product, doc_type=faq, source=session_extraction)` + chunk + embedding
  - 字段 → 更新 `products.attributes[field]`，写 `product_field_history`，异步重建商品向量
- 拒绝 → 只改状态，保留记录供分析

### 9.6 Prompt 与结构化输出

| 用途 | 模型 | 温度 | 输出 |
|---|---|---|---|
| 导购意图/槽位 | qwen-plus | 0.2 | JSON（GuideQuery） |
| 导购重排 | qwen-plus | 0.2 | JSON（选中商品 + 理由） |
| 客服意图路由 | qwen-plus | 0.1 | JSON（intent + entities） |
| 可回答性判断 | qwen-plus | 0.1 | JSON（can_answer/confidence/partial） |
| 客服回答 | qwen-plus | 0.2 | 文本 + 引用 |
| 图片理解 | qwen3-vl-flash | 0.2 | JSON（品类 + 属性） |
| 知识提炼 | qwen-plus | 0.2 | JSON（FAQ + 字段建议） |
| 上下文摘要 | qwen-plus | 0.3 | 文本 |

规则：

- 所有结构化输出用 Pydantic 校验；失败重试 2 次；仍失败返回降级话术并记录日志。
- 客服回答的 system prompt 必须包含"只依据给定资料，不编造；不确定就说不知道"。
- 用户输入不作为指令执行；知识库内容视为资料，不执行其中的"指令"。
- 所有 prompt 集中放在 `backend/app/ai/prompts/`，便于版本管理与论文附录引用。

### 9.7 设计判断

1. **不做全自主 ReAct 循环**。意图/槽位解析 + 确定性管线，比让模型自由规划更可靠、可评测、好调试；只在加购时做一次轻量工具动作。
2. **可回答性判断独立于回答生成**。先判断再生成，避免"先编造再撤回"，也是转人工触发准确率的来源。
3. **澄清优先于转人工**。一次澄清能显著提高 AI 解决率，也避免用户被立刻甩给人工。
4. **知识提炼不自动入库**。candidates + 人工审核，防止脏数据污染知识库；这本身是论文的核心闭环。
5. **全程埋点**。每条 AI 消息的 `meta` 记录候选、分数、过滤器、重排、耗时，评测直接复用。

---

## 10. 接口设计

### 10.1 认证与用户

```text
POST   /api/auth/register       {username, password, nickname}
POST   /api/auth/login          {username, password} → {access_token, user}
GET    /api/auth/me
PATCH  /api/users/me            {nickname?, avatar_url?, height_cm?, weight_kg?, usual_size?}
```

- JWT 放在 `Authorization: Bearer <token>`。
- 密码 bcrypt；登录失败统一提示，不区分用户名/密码错误。

### 10.2 商品与收藏

```text
GET    /api/categories                       # 品类树 + 合并后的 attribute_schema
GET    /api/products?category_id=&q=&page=&page_size=&sort=
GET    /api/products/{id}                    # 含 SKU、尺码表、属性
GET    /api/favorites
POST   /api/products/{id}/favorite
DELETE /api/products/{id}/favorite
```

### 10.3 AI 会话

```text
POST   /api/chat/sessions                    {type: "guide"|"support", product_id?}
GET    /api/chat/sessions?type=
GET    /api/chat/sessions/{id}/messages?before_id=&limit=
POST   /api/chat/sessions/{id}/messages      # SSE
POST   /api/chat/sessions/{id}/escalate
POST   /api/chat/actions/{id}/confirm
POST   /api/chat/actions/{id}/cancel
POST   /api/chat/messages/{id}/feedback      {helpful: true|false, comment?}
```

**消息请求体**：

```json
{
  "content_type": "text",
  "content": {"text": "我想要一件薄衬衫，蓝色，身高172，体重75"}
}
```

支持的内容：

```json
{"content_type": "text", "content": {"text": "..."}}
{"content_type": "image", "content": {"image_url": "...", "text": "类似这种"}}
{"content_type": "voice", "content": {"audio_url": "...", "transcript": "...", "text": "..."}}
```

**消息 content 存储格式**：

```json
{"text": "..."}
{"image_url": "...", "vision": {"category_path": [], "attributes": {}}}
{"audio_url": "...", "transcript": "..."}
{"items": [{"product_id": 1, "title": "...", "image": "...", "price": 199, "recommended_size": "L", "reason": "..."}], "relaxed": []}
{"action_id": 5, "action_type": "add_to_cart", "status": "pending", "payload": {}}
{"event": "agent_joined", "text": "客服已接入"}
```

### 10.4 上传

```text
POST   /api/uploads/image     multipart → {url}
POST   /api/uploads/voice     multipart → {url, transcript}
```

限制：图片 jpg/png/webp ≤ 5MB；音频 webm/mp4/wav ≤ 10MB。

### 10.5 交易

```text
GET    /api/cart
POST   /api/cart/items                 {sku_id, quantity}
PATCH  /api/cart/items/{id}            {quantity?, selected?}
DELETE /api/cart/items/{id}

GET    /api/addresses
POST   /api/addresses
PATCH  /api/addresses/{id}
DELETE /api/addresses/{id}

POST   /api/orders                     {address_id, cart_item_ids: []}
GET    /api/orders?status=
GET    /api/orders/{id}
POST   /api/orders/{id}/pay
POST   /api/orders/{id}/cancel
POST   /api/orders/{id}/confirm        # 确认收货
```

**创建订单**：事务内锁 SKU、校验库存、扣减、创建订单与明细、删除已结算购物车项。

**支付**：`pending_payment → paid`，生成假流水号 `PAY{timestamp}{random}`。

### 10.6 客服端

```text
GET    /api/agent/tickets?status=waiting|connected|closed
GET    /api/agent/tickets/{id}         # 含用户画像、商品、订单、AI 对话、context_summary
POST   /api/agent/tickets/{id}/accept
POST   /api/agent/tickets/{id}/close  {reason?}
POST   /api/agent/tickets/{id}/extract   # 重新触发知识提炼
GET    /api/agent/orders?status=paid
POST   /api/agent/orders/{id}/ship

GET    /api/agent/knowledge/candidates?status=pending
PATCH  /api/agent/knowledge/candidates/{id}          {payload?}
POST   /api/agent/knowledge/candidates/{id}/approve
POST   /api/agent/knowledge/candidates/{id}/reject
```

所有 `/api/agent/*` 要求 role ∈ {agent, admin}。

### 10.7 SSE 事件

```text
event: meta
data: {"intent": "search", "query": {...}, "need_clarify": false}

event: token
data: {"text": "按你的条件，"}

event: products
data: {"items": [...], "relaxed": []}

event: action
data: {"action_id": 5, "action_type": "add_to_cart", "status": "pending", "payload": {...}}

event: citations
data: {"items": [{"doc_type": "faq", "title": "材质说明"}]}

event: answer_meta
data: {"can_answer": true, "confidence": 0.87}

event: done
data: {"message_id": 88, "latency_ms": 1830}

event: error
data: {"code": "LLM_TIMEOUT", "message": "服务繁忙，请稍后再试"}
```

**事件顺序**：

- 导购：`meta → token* → products → done`
- 加购：`meta → action → done`
- 客服能答：`meta → token* → citations → answer_meta → done`
- 客服不能答：`meta → token（固定话术）→ action（转人工）→ answer_meta → done`

### 10.8 WebSocket 协议

```text
连接：/ws/chat/{session_id}   （用户，人工阶段）
      /ws/agent               （客服）

客户端首条消息：
  {"type": "auth", "token": "..."}

客户端消息：
  {"type": "message.send", "content_type": "text", "content": {"text": "..."}}
  {"type": "typing"}
  {"type": "read", "last_message_id": 123}

服务端消息：
  {"type": "auth.ok"}
  {"type": "message.new", "message": {...}}
  {"type": "ticket.created", "ticket": {...}}
  {"type": "ticket.accepted", "ticket": {...}}
  {"type": "ticket.closed", "ticket": {...}}
  {"type": "queue.position", "position": 2}
  {"type": "system", "text": "客服已接入"}
```

- 心跳：30 秒 ping/pong。
- 断线重连：客户端带 `last_message_id`，服务端补发缺失消息。
- 鉴权失败：服务端关闭连接并返回 `auth.failed`。

---

## 11. 页面与交互流程

### 11.1 用户端

#### 11.1.1 登录/注册 `/login`

- 用户名 + 密码；注册后自动登录。
- 演示账号预置：`demo / demo123`。

#### 11.1.2 AI 导购 `/`（默认页）

不设独立首页，发现入口放在聊天空状态：

- 空状态：AI 问候 + 身材档案提示 + 3 条示例问法 + 4 个品类快捷入口 + 6~8 个热门商品卡
- 点示例问法/品类 → 直接发送查询；点商品卡 → 商品详情
- 顶部右上角：购物车入口
- 会话列表抽屉：历史导购会话
- 聊天区：消息、商品卡片、澄清快捷选项、加购确认卡
- 输入区：文本框、图片按钮、语音按钮、发送
- 语音：录音 → 转写 → 回填输入框 → 用户确认发送
- 图片：上传 → 缩略图 → 发送 → AI 理解并检索
- 商品卡片：图片、标题、价格、推荐尺码、[详情] [加购]

#### 11.1.3 商品详情 `/product/:id`

- 图片轮播
- 标题、价格、品牌、销量
- 颜色/尺码选择（SKU）、库存
- 尺码推荐卡片：根据档案身高体重给出建议
- 属性表、尺码表
- 收藏按钮
- [加入购物车] [立即购买]
- 底部操作栏「客服」入口 → 打开独立客服页 `/product/:id/support`（不做全局悬浮客服）

#### 11.1.4 商品客服 `/product/:id/support`

- AI 问答：流式文本、引用来源、有帮助/没帮助
- 不可答：固定话术 + 转人工按钮
- 转人工：排队状态、客服接入提示
- 人工会话：文本/图片/语音、结束提示、评分
- 断线重连提示

#### 11.1.5 购物车 `/cart`

- SKU 行：图片、标题、颜色/尺码、单价、数量、库存状态
- 勾选、全选、删除
- 合计、去结算

#### 11.1.6 结算 `/checkout`

- 地址选择/新增
- 商品清单、金额
- [提交订单] → 创建订单 → 跳转订单详情
- 模拟支付按钮

#### 11.1.7 订单 `/orders`、`/orders/:id`

- 列表：全部 / 待支付 / 待发货 / 已发货 / 已完成
- 详情：状态、商品快照、地址快照、金额、时间线
- 操作：支付、取消、确认收货

#### 11.1.8 我的 `/me`

- 头像、昵称、身高/体重/常穿尺码（可编辑）
- 收藏列表
- 导购会话历史
- 订单入口
- 地址管理
- 退出登录

#### 11.1.9 视觉风格（前端实现基准）

以 `docs/mockups/chat-discovery.html`（截图 `chat-discovery.png`）为基准。完整页面样板（静态，仅用于评审）见 `docs/mockups/screens-user.png`（12 个用户端页面）与 `docs/mockups/screens-agent.png`（3 个客服端页面），HTML 源文件在同一目录：

- 主色 `#FF5A1F`，品牌渐变 `#FF8A3D → #FF4D2E`
- 页面背景 `#F6F7F9`；卡片纯白、圆角 14px、轻阴影
- 文字：主文字 `#22262A`，次要 `#9AA0A6`，价格 `#FF4D2E`
- 商品卡：2 列网格，图片 1:1 裁切，标题两行截断，底部价格 + 销量
- 快捷入口：胶囊 chips + 四宫格品类入口
- 底部导航：两个 Tab（AI 找货 / 我的），高度 56px
- 输入栏：图片/语音按钮 + 胶囊输入框 + 圆形发送按钮
- 用 Vant 4 组件实现，不直接复用 mockup 的 HTML；图标按钮落地时放大到 ≥44×44px 触控区

### 11.2 客服端

#### 11.2.1 队列 `/agent/queue`

- 待接入 / 进行中 / 已结束
- 工单卡片：用户、商品、等待时长、最后一条消息
- 新工单 WebSocket 实时提醒

#### 11.2.2 会话 `/agent/chat/:ticketId`

- 左侧/顶部：用户画像（身高体重）、商品卡片、订单列表、context_summary
- 中间：AI 阶段 + 人工阶段完整消息
- 底部：回复框（文本/图片/语音）
- 操作：接入、结束会话

#### 11.2.3 订单 `/agent/orders`

- 已支付订单列表
- [模拟发货] 按钮

#### 11.2.4 知识审核 `/agent/knowledge`

- 待审核候选列表：类型、内容、置信度、证据摘录、重复标记
- 编辑、通过、拒绝
- 已处理历史

### 11.3 关键流程

**导购到下单**：

```text
登录 → AI 聊天 → 输入需求 → 商品卡 → 加购确认 → 购物车 → 结算 → 创建订单 → 模拟支付 → 等待发货
```

**客服到知识回灌**：

```text
商品详情 → AI 客服 → 提问 → 不可答 → 转人工 → 排队 → 客服接入
→ 人工对话 → 结束 → 用户评分 → AI 提炼 → 客服审核 → 通过入库
```

---

## 12. 状态机

### 12.1 订单

```text
pending_payment ──pay(模拟)──> paid ──ship(客服端)──> shipped ──confirm(用户)──> completed
       │
       └──cancel / 15min timeout──> cancelled
```

规则：

- 创建订单时锁库存并扣减；取消/超时恢复。
- 支付幂等：已支付再次调用直接返回成功。
- 发货：仅 `paid` 可发货。
- 确认收货：仅 `shipped` 可确认。
- 超时：`expires_at` 到期后惰性取消（列表/详情/支付时检查）+ FastAPI lifespan 内的 asyncio 定时任务兜底（每分钟扫描一次）。
- 支付成功后累加 `products.sales_count`，用于推荐热度排序。

### 12.2 会话与工单

```text
chat_session:
active ──escalate──> waiting_human ──agent_accept──> human ──close──> closed

support_ticket:
waiting ──accept──> connected ──close──> closed
```

### 12.3 加购动作

```text
pending ──confirm──> confirmed ──execute──> executed
pending ──cancel──> cancelled
pending ──execute_fail──> failed
```

- 执行失败（库存不足/下架）保留失败原因，允许用户取消或改选。

---

## 13. 部署方案

### 13.1 Docker Compose

```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    volumes: [pgdata:/var/lib/postgresql/data]
    environment:
      POSTGRES_DB: shop
      POSTGRES_USER: shop
      POSTGRES_PASSWORD: ${DB_PASSWORD}

  backend:
    build: ./backend
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
    env_file: .env
    volumes:
      - ./backend/static:/app/static
      - ./backend/uploads:/app/uploads
    depends_on: [db]

  nginx:
    image: nginx:alpine
    ports: ["80:80", "443:443"]
    volumes:
      - ./frontend/dist:/usr/share/nginx/html
      - ./backend/static:/usr/share/nginx/static
      - ./backend/uploads:/usr/share/nginx/uploads
      - ./deploy/nginx.conf:/etc/nginx/conf.d/default.conf
      - ./deploy/certs:/etc/letsencrypt
    depends_on: [backend]
```

### 13.2 Nginx

- `/` → Vue SPA，`try_files $uri $uri/ /index.html`
- `/api/` → `proxy_pass http://backend:8000`
- `/ws/` → WebSocket upgrade
- `/static/`、`/uploads/` → 静态文件
- HTTP 301 → HTTPS

### 13.3 环境变量

```text
DASHSCOPE_API_KEY=
DATABASE_URL=postgresql+asyncpg://shop:password@db:5432/shop
JWT_SECRET_KEY=
JWT_EXPIRE_MINUTES=10080
UPLOAD_DIR=/app/uploads
STATIC_DIR=/app/static
```

### 13.4 首次部署

1. 安装 Docker / Docker Compose
2. 前端 `npm run build` 生成 `frontend/dist`
3. 配置域名解析与 Certbot 证书
4. `docker compose up -d --build`
5. `alembic upgrade head`
6. 运行种子脚本：品类、商品、SKU、知识库、演示账号
7. 生图产物放入 `backend/static/products/`
8. 健康检查 `/api/health`

### 13.5 运维

- 日志：uvicorn access/error + Nginx；保留 7 天
- 备份：每日 `pg_dump` 到独立目录
- 监控：健康检查 + 简单磁盘/内存告警（可选）
- CORS 只允许前端域名；上传校验类型与大小；DashScope Key 只存服务端
- 服务器：2C4G，Ubuntu 22.04

---

## 14. 测试与评测

### 14.1 测试策略

| 层级 | 工具 | 覆盖 |
|---|---|---|
| 单元测试 | pytest | 认证、JSONB 过滤、品类树、尺码规则、订单状态机、库存并发、转人工规则 |
| 集成测试 | pytest + httpx + 测试库 | API 端点、SSE 事件顺序、WebSocket 消息、订单事务 |
| E2E | Playwright | 登录→导购→加购→下单→支付→发货→收货；客服→转人工→接入→结束→审核入库 |
| 人工验收 | 演示脚本 | 10 条固定演示路径 |

- AI 客户端通过依赖注入 mock，单元测试不依赖外网。
- 并发测试：两个请求同时创建同一 SKU 的订单，验证只有一个成功。

### 14.2 评测集与指标

**数据集**（`backend/scripts/eval/`）：

| 文件 | 数量 | 内容 |
|---|---|---|
| `guide_queries.json` | 60 | 查询 + 期望品类/过滤 + 期望商品 ID |
| `support_qa.json` | 30 | 商品 + 问题 + 期望答案要点 + 来源文档 |
| `unanswerable.json` | 20 | 知识库外问题，期望转人工 |
| `size_cases.json` | 20 | 身高体重 + 商品 + 期望尺码 |

**指标**：

| 指标 | 定义 |
|---|---|
| NL→filter 准确率 | 品类与关键过滤条件完全匹配的比例 |
| Recall@5 | 相关商品出现在前 5 的比例 |
| MRR | 第一个相关商品排名的倒数均值 |
| 答案忠实度 | LLM-as-judge 1~5 分 + 人工抽检 20% |
| 转人工 precision/recall | 应转与实转的匹配 |
| AI 解决率（containment rate） | 未转人工就结束的客服会话占比 |
| CSAT | 会话结束评分均值 |
| 尺码准确率 | 推荐尺码与期望一致的比例 |
| 任务成功率 | 端到端完成导购/下单/客服任务的比例 |

**采集方式**：

- AI 消息 `meta` 记录候选、分数、过滤器、重排、耗时。
- 转人工记录触发原因。
- 用户评分与"有帮助/没帮助"写库。
- 评测脚本批量跑数据集，输出 CSV/Markdown 报告。

### 14.3 消融实验

| 实验 | 开关 |
|---|---|
| 纯结构化 vs 纯向量 vs 混合检索 | `RETRIEVAL_MODE` |
| 有无 LLM 重排 | `RERANK_ENABLED` |
| 有无主动澄清 | `CLARIFY_ENABLED` |
| 有无品类级知识复用 | 知识库配置 |
| 有无知识回灌 | 对比回灌前后同类问题解决率 |

---

## 15. 里程碑

按 2026 年 11 月中旬启动、2027 年 5 月中旬答辩排期，共 26 周（23 周开发 + 3 周缓冲）：

| 阶段 | 周 | 内容 | 验收 |
|---|---|---|---|
| M0 | 1 | 仓库、Docker、DB schema、认证骨架 | 能登录、能连库 |
| M1 | 2~4 | 品类/商品/SKU、种子数据、AI 生图、商品详情 | 聊天推荐可进商品详情 |
| M2 | 5~6 | 购物车、地址、订单、模拟支付、发货/收货 | 完整下单闭环 |
| M3 | 7~8 | 知识库构建、RAG 检索、商品客服问答 | 客服能答商品/政策问题 |
| M4 | 9~11 | 导购聊天、意图槽位、澄清、混合检索、尺码 | 自然语言找货可用 |
| M5 | 12~13 | 图片理解、ASR、AI 加购 | 多模态输入 + 加购闭环 |
| M6 | 14~15 | 转人工、排队、客服端、上下文摘要 | 双端实时会话跑通 |
| M7 | 16~17 | 知识提炼、审核、入库、审计 | 闭环完整可演示 |
| M8 | 18~20 | 评测集、消融实验、指标、修复 | 论文实验数据齐 |
| M9 | 21~23 | 部署、论文定稿、演示排练 | 线上可访问、论文定稿 |
| 缓冲 | 24~26 | 答辩准备、意外处理 | — |

**排期说明**

- 寒假约在第 11~14 周，覆盖 M4 尾巴、M5、M6，把最耗时的 AI 联调放在全天投入的四周。
- 论文初稿在寒假完成；M9 只做定稿、排版和排练。
- 第 17 周功能冻结，之后只修 bug，不加功能。
- 第 8 周检查点：导购链路没跑通，就先砍图片输入，保留语音/文本。

**时间不足时的裁剪顺序**：收藏 → 客服评分与统计面板 → 图片输入（保留语音/文本）→ 语音输入（保留文本）→ 发货环节（订单直接完成）。导购、RAG 客服、转人工、知识闭环不砍。

---

## 16. 风险与应对

| 风险 | 影响 | 应对 |
|---|---|---|
| LLM 输出 JSON 不稳定 | 解析失败、流程中断 | Pydantic 校验 + 重试 2 次 + 降级话术 |
| RAG 编造 | 客服答错、可信度下降 | 可回答性判断 + 引用 + 低温度 + 忠实度抽检 |
| 知识库质量差 | 大量转人工 | 内容清单 + 品类级 FAQ 复用 + 去重 + 抽检 |
| 知识提炼噪声 | 审核负担、污染知识库 | candidates 闸门 + 相似度去重 + 置信度阈值 + 审核记录 |
| iOS 录音兼容性 | 语音不可用 | 后端 ASR + 文本兜底 + HTTPS |
| 单 worker WebSocket | 无法水平扩展 | 固定 1 worker + 重连补消息 + realtime 接口化 |
| 生图质量不稳 | 商品卡观感差 | 批量生成后筛图 + 关键商品重生成 + 占位图兜底 |
| 订单并发 | 超卖 | `SELECT ... FOR UPDATE` + 行锁 + 并发测试 |
| 时间超支 | 无法按期答辩 | 按裁剪顺序砍功能 + 里程碑每周检查 |
| 答辩网络故障 | 演示失败 | 提前预热 + 降级文案 + 录屏备份 |

---

## 17. 附录

### 17.1 尺码表示例（服装）

```json
{
  "type": "clothing",
  "unit": "cm",
  "rows": [
    {"size": "S", "height": [155, 165], "weight": [45, 55], "chest": [82, 88], "waist": [68, 74]},
    {"size": "M", "height": [165, 172], "weight": [55, 65], "chest": [88, 94], "waist": [74, 80]},
    {"size": "L", "height": [170, 178], "weight": [65, 75], "chest": [94, 100], "waist": [80, 86]},
    {"size": "XL", "height": [176, 184], "weight": [75, 85], "chest": [100, 106], "waist": [86, 92]}
  ]
}
```

匹配：身高与体重同时命中区间；命中多行取区间中心归一化距离最小；并列取较大尺码；都不命中取最近并提示试穿。

### 17.2 尺码表示例（鞋靴）

```json
{
  "type": "shoes",
  "unit": "mm",
  "rows": [
    {"size": "40", "foot_length": [245, 250]},
    {"size": "41", "foot_length": [250, 255]},
    {"size": "42", "foot_length": [255, 260]},
    {"size": "43", "foot_length": [260, 265]}
  ]
}
```

鞋靴没有身高体重维度，用户需提供脚长；未提供时提示测量方法。

### 17.3 SSE / WebSocket 示例

**SSE 导购**：

```text
event: meta
data: {"intent":"search","query":{"category_path":["服装","衬衫"],"filters":{"color":["蓝色"],"thickness":["薄款"]}},"need_clarify":false}

event: token
data: {"text":"按你的条件，我筛出了这几款薄款蓝色衬衫，"}

event: products
data: {"items":[{"product_id":12,"title":"男士纯棉薄款衬衫","image":"/static/products/12_1.jpg","price":199,"recommended_size":"L","reason":"薄款纯棉，版型常规"}],"relaxed":[]}

event: done
data: {"message_id":88,"latency_ms":1830}
```

**WebSocket 人工会话**：

```text
C: {"type":"auth","token":"..."}
S: {"type":"auth.ok"}
S: {"type":"ticket.accepted","ticket":{"id":3,"status":"connected"}}
S: {"type":"system","text":"客服已接入"}
C: {"type":"message.send","content_type":"text","content":{"text":"这件有货吗？"}}
S: {"type":"message.new","message":{"id":101,"sender_type":"agent","content":{"text":"有货的，蓝色 L 码还有 8 件。"}}}
S: {"type":"ticket.closed","ticket":{"id":3,"status":"closed"}}
```

### 17.4 术语表

| 术语 | 说明 |
|---|---|
| RAG | 检索增强生成：先检索知识，再让模型基于知识回答 |
| RRF | Reciprocal Rank Fusion，多路检索结果融合算法 |
| HNSW | 向量近似最近邻索引结构 |
| Slot Filling | 槽位填充：把用户自然语言解析成结构化条件 |
| Containment Rate | AI 解决率：未转人工就结束的会话占比 |
| CSAT | 用户满意度评分 |
| Human-in-the-loop | 人工在环：AI 产出经人工审核后再生效 |
| SSE | Server-Sent Events，服务端单向流式推送 |
| SKU | 最小可售单元（颜色 + 尺码） |

---

## 18. 待评审要点

> **2026-11-12 评审完成**：以下 6 项全部通过；页面样板已确认（见 11.1.9）；Agent Assist 明确不做。下一步进入实现计划。

请重点确认以下内容，确认后进入实现计划：

1. 17 张表的结构是否够用，是否有缺失字段
2. 4 个一级品类 + 叶子品类的划分是否符合预期
3. 知识库内容清单的工作量是否可接受
4. 导购/客服两条管线的交互是否符合预期
5. 26 周里程碑（23 周开发 + 3 周缓冲）是否与现实时间匹配
6. 非目标清单里是否有你希望保留的功能
