# M1 商品域 + 种子数据 + 商品详情 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **实施状态（2026-11-13）：已完成。** 由于真实 CSV token 与初稿假设不同，叶子可筛选属性、部分任务顺序和测试细节在实施时做了调整；以文末「实施结果与计划偏差」和实际代码为准。

**Goal:** 建立品类/商品/SKU/收藏四张表与 Alembic 迁移，生成 300 个商品、约 1100 条 SKU 的可重复种子数据，提供品类树、商品列表/筛选/分页、商品详情、收藏接口，并完成 AI 找货 Tab 的可复用商品发现组件、分类商品列表、商品详情与收藏页。

**Architecture:** 后端新增 `modules/catalog`（models / schemas / service / router），沿用现有 FastAPI + async SQLAlchemy + Pydantic v2 分层；商品图通过 `/static` 挂载，Vite 开发代理 `/static` 到 8100。种子拆成两步：`build_catalog_seed.py` 从 `tools/image-batch/data/*.csv` 一次性生成 JSON（价格/销量/库存写死在 JSON），`seed_catalog.py` 只把 JSON upsert 到数据库，不重算任何值。前端新增可复用 `ProductDiscoveryPanel` 嵌入现有 AI 找货 Tab，新增 `/category/:id`、`/product/:id`、`/favorites` 三个顶层路由；复用 M0 的 auth store、Axios、Pinia 与 TabbarLayout。

**Tech Stack:** Python 3.12 + FastAPI + SQLAlchemy 2.0 + Alembic + asyncpg + PostgreSQL 16/pgvector + PyJWT + bcrypt + pgvector；Vue 3 + Vite 6 + TypeScript + Pinia + Vue Router + Vant 4 + Axios；pytest + httpx + Playwright；Docker Compose（开发库 5433、后端 8100、前端 5175）。

---

## 0. 范围、契约与验收

### 0.1 用户已确认的 7 条决定

1. `products` 增加 `product_code VARCHAR(20) UNIQUE NOT NULL`（C001/S001/B001/A001），用于按 CSV ID 幂等 upsert；同步改设计文档 §7.2.2 与迁移。
2. 种子拆两步：`build_catalog_seed.py`（CSV→JSON，一次性生成价格/销量/库存，价格按品类区间，`original_price >= price`）与 `seed_catalog.py`（JSON→DB upsert）。JSON 是源，导入时不重算哈希；build 默认不覆盖已存在的 JSON，需 `--force`。
3. `design_detail` 不做大而全的可筛选枚举；`key_feature` 作为 `key_features` tags 展示；每个叶子只保留 2~3 个真正可筛选的属性。
4. SKU 按实际尺码，接受约 1100；不给钱包/墨镜/项链凑 5 码；单尺码商品显示“均码”并隐藏尺码选择；同步把设计文档 §8.2 的 3000~5000 改成实际范围，注明“一商品一图一色”。
5. 接口补 DTO：分页 `{items,total,page,page_size}`；`sort` 只做 `recommended/price_asc/price_desc`；父品类默认含子类；收藏 POST/DELETE 幂等，返回 `{favorited:bool}`；商品详情公开，登录时带 `is_favorited`。
6. `embedding` 列建好但 M1 不调用 DashScope，保持 NULL；`/static` 挂载 + Vite 代理 + 种子校验 300 张图存在。
7. AI 找货 Tab 的商品入口做成可复用组件，不新建独立 Home 路由；M4 直接嵌进聊天空状态。

### 0.2 M1 包含

- `categories`、`products`、`product_skus`、`favorites` 四表与 Alembic `20261113_0002_create_catalog`。
- 品类树接口（含父级 + 叶子合并后的 `attribute_schema`）。
- 商品列表接口：`category_id`、`q`、`page`、`page_size`、`sort`；父品类含子类。
- 商品详情接口：SKU、尺码表、属性、分类名、`is_favorited`。
- 收藏接口：列表、添加、删除；全部要求登录，幂等。
- 4 个一级品类 + 34 个叶子品类种子 JSON；300 个商品；1108 条 SKU；300 张已有商品图引用。
- 前端：可复用 `ProductDiscoveryPanel` 嵌入 `/`；`/category/:id` 列表；`/product/:id` 详情；`/favorites` 收藏页；Me 页“我的收藏”入口。
- 后端 pytest、前端 `npm run build`、Playwright “列表→详情→收藏” E2E。
- 更新设计文档、README、`docs/progress.md`、`docs/implementation-handoff.md`。

### 0.3 M1 不包含

- 购物车、地址、订单、模拟支付/发货（M2）。
- 收藏以外的 AI 会话、RAG 客服、转人工、知识库（M3~M7）。
- 尺码推荐算法（M4）；详情页只展示尺码表和尺码选择。
- DashScope embedding / 向量检索；`products.embedding` 建列但保持 NULL。
- AI 生图；只使用 `backend/static/products` 已有图片。
- 商品评价、好评率、优惠券。

### 0.4 接口契约

```text
GET    /api/categories
GET    /api/products?category_id=&q=&page=&page_size=&sort=
GET    /api/products/{id}
GET    /api/favorites
POST   /api/products/{id}/favorite
DELETE /api/products/{id}/favorite
```

- `GET /api/categories`：返回 4 个一级节点数组；每个节点含 `children`。每个节点的 `attribute_schema` 是“父级公共属性 + 自身叶子属性”合并后的结果，同 key 以叶子为准。
- `GET /api/products`：公开；返回 `{items,total,page,page_size}`。`page` 默认 1，`page_size` 默认 20、最大 50。`sort` 仅 `recommended|price_asc|price_desc`，默认 `recommended`（销量降序、id 升序）。`category_id` 传一级品类时默认包含其全部叶子品类。
- `GET /api/products/{id}`：公开；只返回 `status=on_sale`。带 `Authorization: Bearer <token>` 且 token 有效时返回 `is_favorited`，无效/缺失 token 时按未登录处理，不报 401。
- `GET /api/favorites`：需要登录；返回当前用户收藏的商品摘要数组，按收藏时间倒序。
- `POST /api/products/{id}/favorite`：需要登录；商品不存在/已下架返回 404；已收藏时仍返回 `{favorited:true}`。
- `DELETE /api/products/{id}/favorite`：需要登录；商品不存在/已下架返回 404；未收藏时仍返回 `{favorited:false}`。

### 0.5 数据契约

- `products.product_code` 唯一；种子按该字段 upsert，保证重复导入不改变商品 id，从而不破坏收藏。
- 一商品一图一色：`products.main_image = /static/products/{product_code}_{color}.png`，`images = [main_image]`。
- 服装/鞋靴每商品 5 个尺码；箱包/配饰按实际 1~4 个尺寸；单尺码用“均码”。
- 当前种子 SKU 固定为 **1108**：服装 375、鞋靴 375、箱包 209、配饰 149。
- `products.attributes.key_features` 是 CSV `key_feature` 的原始 token 数组，仅展示，不参与筛选。
- 叶子 schema 的 2~3 个可筛选属性由 `attribute_rules` 生成：命中 token 用 token 对应值，未命中用 `default`。选项只来自该叶子的规则值集合，不造几十个无关选项。
- `products.embedding` 为 `vector(1024) NULL`，M1 不写入。

### 0.6 验收标准

- `cd backend && python -m pytest` 全部通过；新增测试覆盖四表 schema、品类树、商品列表/筛选/分页/排序、详情、收藏幂等、种子幂等与图片校验。
- `cd frontend && npm run build` 通过（vue-tsc 无报错）。
- `cd frontend && npm run test:e2e` 通过；新增“列表→详情→收藏”用例；M0 认证 E2E 不回归。
- 手工验收：登录 demo → AI 找货 Tab 看到 4 个品类入口和热门商品 → 进分类列表 → 进商品详情 → 收藏 → 我的收藏看到该商品 → 取消收藏。
- `python -m scripts.seed_catalog` 连续执行两次，品类/商品/SKU 数量不变，收藏不丢；300 张图片全部存在。
- 设计文档 §7.2.2、§8.1、§8.2、§10.2 与实现一致。

---

## 1. 文件结构

```text
graduation-project-new/
├── backend/
│   ├── requirements.txt                         # + pgvector
│   ├── alembic/versions/
│   │   └── 20261113_0002_create_catalog.py      # 新建
│   ├── app/
│   │   ├── main.py                              # + catalog router + /static mount
│   │   ├── models.py                            # + catalog models import
│   │   └── modules/
│   │       ├── auth/deps.py                     # + get_current_user_optional
│   │       └── catalog/                         # 新建
│   │           ├── __init__.py
│   │           ├── models.py
│   │           ├── schemas.py
│   │           ├── service.py
│   │           └── router.py
│   ├── seeds/catalog/                           # 新建，提交 git
│   │   ├── categories.json
│   │   └── products.json                        # build_catalog_seed.py 生成
│   ├── scripts/
│   │   ├── build_catalog_seed.py                # 新建
│   │   └── seed_catalog.py                      # 新建
│   └── tests/
│       ├── conftest.py                          # + clean_catalog/seeded_catalog
│       ├── test_catalog_schema.py               # 新建
│       ├── test_catalog_api.py                  # 新建
│       ├── test_catalog_seed.py                 # 新建
│       └── unit/test_catalog_seed_build.py      # 新建
└── frontend/
    ├── vite.config.ts                           # + /static proxy
    ├── src/
    │   ├── api/catalog.ts                       # 新建
    │   ├── types/catalog.ts                     # 新建
    │   ├── stores/catalog.ts                    # 新建
    │   ├── stores/favorites.ts                  # 新建
    │   ├── utils/format.ts                      # 新建
    │   ├── utils/colors.ts                      # 新建
    │   ├── components/catalog/
    │   │   ├── ProductImage.vue                 # 新建
    │   │   ├── ProductCard.vue                  # 新建
    │   │   └── ProductDiscoveryPanel.vue        # 新建
    │   ├── views/user/
    │   │   ├── HomeView.vue                     # 修改：嵌入发现组件
    │   │   ├── CategoryView.vue                 # 新建
    │   │   ├── ProductDetailView.vue            # 新建
    │   │   ├── FavoritesView.vue                # 新建
    │   │   └── MeView.vue                       # 修改：收藏入口
    │   ├── router/index.ts                      # + 3 个顶层路由
    │   └── main.ts                              # 401 时清空收藏 store
    └── tests/e2e/catalog.spec.ts                # 新建
```

---

## 2. 执行前置

- [ ] **Step 1: 确认分支与工作区**

```bash
cd /d/develop/graduation-project-new
git status --short
git branch --show-current
```

Expected: 工作区干净，当前分支 `m1-product-catalog`。

- [ ] **Step 2: 确认数据库、后端端口、商品图**

```bash
cd deploy
docker compose -f docker-compose.dev.yml up -d --wait
cd ../backend
source .venv/Scripts/activate
python -m alembic upgrade head
ls static/products | wc -l
```

Expected: `alembic upgrade head` 成功；`static/products` 输出 `300`。

- [ ] **Step 3: 安装 pgvector Python 包**

```bash
cd /d/develop/graduation-project-new/backend
source .venv/Scripts/activate
pip install "pgvector>=0.3.6"
```

Expected: `Successfully installed pgvector-...` 或 `Requirement already satisfied`。

---

## 3. 数据设计

### 3.1 表结构

**categories**

| 字段 | 类型 | 约束 |
|---|---|---|
| id | BIGSERIAL | PK |
| parent_id | BIGINT NULL | FK categories.id, ON DELETE CASCADE |
| name | VARCHAR(50) | NOT NULL |
| slug | VARCHAR(50) | NOT NULL, UNIQUE |
| level | SMALLINT | NOT NULL, CHECK level IN (1,2) |
| attribute_schema | JSONB | NOT NULL, DEFAULT '{}' |
| size_chart_template | JSONB | NULL |
| sort_order | INT | NOT NULL, DEFAULT 0 |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL, now() |

**products**

| 字段 | 类型 | 约束 |
|---|---|---|
| id | BIGSERIAL | PK |
| product_code | VARCHAR(20) | NOT NULL, UNIQUE（C001/S001/B001/A001） |
| category_id | BIGINT | NOT NULL, FK categories.id |
| title | VARCHAR(200) | NOT NULL |
| description | TEXT | NULL |
| brand | VARCHAR(100) | NULL |
| price | NUMERIC(10,2) | NOT NULL |
| original_price | NUMERIC(10,2) | NULL, >= price |
| main_image | VARCHAR(500) | NULL |
| images | JSONB | NOT NULL, DEFAULT '[]' |
| attributes | JSONB | NOT NULL, DEFAULT '{}' |
| size_chart | JSONB | NULL |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'on_sale' |
| sales_count | INT | NOT NULL, DEFAULT 0 |
| embedding | vector(1024) | NULL |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL, now() |

**product_skus**

| 字段 | 类型 | 约束 |
|---|---|---|
| id | BIGSERIAL | PK |
| product_id | BIGINT | NOT NULL, FK products.id, ON DELETE CASCADE |
| color | VARCHAR(30) | NOT NULL |
| size | VARCHAR(20) | NOT NULL |
| stock | INT | NOT NULL, DEFAULT 0, CHECK stock >= 0 |
| price_override | NUMERIC(10,2) | NULL |
| sku_code | VARCHAR(50) | NOT NULL, UNIQUE |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'active' |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL, now() |

约束：`UNIQUE(product_id, color, size)`。

**favorites**

| 字段 | 类型 | 约束 |
|---|---|---|
| id | BIGSERIAL | PK |
| user_id | BIGINT | NOT NULL, FK users.id, ON DELETE CASCADE |
| product_id | BIGINT | NOT NULL, FK products.id, ON DELETE CASCADE |
| created_at | TIMESTAMPTZ | NOT NULL, now() |

约束：`UNIQUE(user_id, product_id)`。

索引：`ix_categories_parent_id`、`ix_products_category_id`、`ix_products_attributes_gin`（GIN）、`ix_products_embedding_hnsw`（HNSW `vector_cosine_ops`）、`ix_product_skus_product_id`、`ix_favorites_user_id`。

### 3.2 34 个叶子 schema

基础 schema 放在一级品类，叶子只放 2~3 个可筛选属性；`key_features` 由一级品类的公共 schema 声明为 tags，不参与筛选。`规则` 列表示 `token → 值`，未命中 token 时使用 `default`。

**服装（clothing）公共属性**

| key | label | options | filterable |
|---|---|---|---|
| color | 颜色 | 黑色/白色/米白/浅灰/深灰/藏青/蓝色/浅蓝/卡其/棕色/绿色/酒红/驼色/粉色/黄色 | true |
| material | 材质 | 亚麻/抓绒/棉/棉混纺/棉麻/涤纶/牛仔/牛津纺/真丝/纯棉/羊毛/羊绒混纺/聚酯纤维/腈纶/莫代尔/锦纶/雪纺 | true |
| fit | 版型 | 修身/常规/宽松/直筒/锥形/A字/包臀 | true |
| thickness | 厚薄 | 薄款/常规/加厚 | true |
| style | 风格 | 休闲/基础/复古/度假/户外/正式/运动/通勤 | true |
| gender | 适用性别 | 男/女/中性 | true |
| season | 季节 | 春/夏/秋/冬 | true |
| size | 尺码 | S/M/L/XL/XXL | true |
| key_features | 设计细节 | 无 options，type=tags | false |

服装叶子：

| 叶子 | 可筛选属性（key/label/options） | 规则（token→值；default） |
|---|---|---|
| 衬衫 | collar_type/领型/翻领,立领；sleeve_length/袖长/长袖,短袖；pattern/图案/纯色,条纹,格纹 | 翻领→翻领，default 立领；短袖→短袖，default 长袖；条纹→条纹、格纹→格纹，default 纯色 |
| T恤 | collar_type/领型/圆领,V领；sleeve_length/袖长/短袖,长袖；shoulder/肩型/落肩,常规肩 | 圆领→圆领，default V领；短袖→短袖，default 长袖；落肩→落肩，default 常规肩 |
| 裤装 | waist_type/腰型/高腰,中腰；length/裤长/九分,长裤；pocket_type/口袋/斜插袋,后口袋,无口袋 | 高腰→高腰，default 中腰；九分→九分，default 长裤；斜插袋→斜插袋、后口袋→后口袋，default 无口袋 |
| 连衣裙 | neckline/领型/V领,圆领；length/裙长/中长款,短款；waist/腰型/收腰,直筒 | V领→V领，default 圆领；中长款→中长款，default 短款；收腰→收腰，default 直筒 |
| 外套 | collar_type/领型/翻领,立领；length/衣长/中长款,短款；closure/门襟/双排扣,单排扣 | 翻领→翻领，default 立领；中长款→中长款，default 短款；双排扣→双排扣，default 单排扣 |
| 针织衫 | collar_type/领型/圆领,V领；sleeve_length/袖长/长袖,短袖；pattern/图案/麻花,条纹,纯色 | 圆领→圆领，default V领；长袖→长袖，default 短袖；麻花纹理→麻花、撞色条纹→条纹，default 纯色 |
| 卫衣 | hood/帽型/连帽,无帽；drawstring/抽绳/有,无；pocket/口袋/袋鼠口袋,无口袋 | 连帽→连帽，default 无帽；抽绳→有，default 无；袋鼠口袋→袋鼠口袋，default 无口袋 |
| 半身裙 | waist_type/腰型/高腰,中腰；length/裙长/中长款,短款；silhouette/版型/A字,直筒,包臀 | 高腰→高腰，default 中腰；中长款→中长款，default 短款；A字摆→A字，default 直筒 |
| 西装 | lapel/领型/平驳领,戗驳领；closure/门襟/单排扣,双排扣；length/衣长/常规,中长款 | 平驳领→平驳领，default 戗驳领；单排扣→单排扣，default 双排扣；default 常规 |
| 风衣 | collar_type/领型/翻领,立领；closure/门襟/双排扣,单排扣；length/衣长/中长款,短款 | 翻领→翻领，default 立领；双排扣→双排扣，default 单排扣；中长款→中长款，default 短款 |

**鞋靴（footwear）公共属性**

| key | label | options | filterable |
|---|---|---|---|
| color | 颜色 | 黑色/白色/米白/灰色/藏青/棕色/卡其/绿色/酒红/粉色 | true |
| material | 材质 | EVA/帆布+橡胶/棉/漆皮/皮革/皮革+橡胶/织物/绒面/绒面+橡胶/网布+EVA/网布+橡胶/飞织+EVA | true |
| style | 风格 | 休闲/复古/居家/度假/正式/跑步/运动/通勤 | true |
| gender | 适用性别 | 男/女/中性 | true |
| size | 尺码 | 35/36/37/38/39/40/41/42/43 | true |
| key_features | 设计细节 | tags | false |

鞋靴叶子：

| 叶子 | 可筛选属性 | 规则 |
|---|---|---|
| 运动鞋 | closure/闭合/系带,一脚蹬；sole/鞋底/厚底,平底；upper/鞋面/网面,皮革 | 系带→系带，default 一脚蹬；厚底→厚底，default 平底；透气网面→网面，default 皮革 |
| 休闲鞋 | toe_shape/鞋头/圆头,尖头；closure/闭合/系带,一脚蹬；sole/鞋底/软底,橡胶底 | 圆头→圆头，default 尖头；系带→系带，default 一脚蹬；软底→软底、橡胶大底→橡胶底，default 橡胶底 |
| 皮鞋 | toe_shape/鞋头/圆头,尖头；closure/闭合/系带,一脚蹬；sole/鞋底/橡胶底,皮革底 | 圆头→圆头，default 尖头；系带→系带，default 一脚蹬；橡胶鞋底→橡胶底，default 皮革底 |
| 靴子 | shaft_height/筒高/短筒,中筒；heel/鞋跟/粗跟,平底；closure/闭合/松紧侧片,系带 | 短筒→短筒，default 中筒；粗跟→粗跟，default 平底；松紧侧片→松紧侧片，default 系带 |
| 帆布鞋 | closure/闭合/系带,一脚蹬；sole/鞋底/硫化底,橡胶底；height/帮高/低帮,高帮 | 系带→系带，default 一脚蹬；硫化底→硫化底，default 橡胶底；低帮→低帮，default 高帮 |
| 凉鞋 | closure/闭合/搭扣,一脚蹬；toe_shape/鞋头/露趾,包头；sole/鞋底/轻便,厚底 | 搭扣→搭扣，default 一脚蹬；露趾→露趾，default 包头；轻便鞋底→轻便，default 厚底 |
| 拖鞋 | toe_shape/鞋头/包头,露趾；sole/鞋底/软底,防滑 | 包头→包头，default 露趾；软底→软底、防滑→防滑，default 防滑 |
| 高跟鞋 | toe_shape/鞋头/尖头,圆头；heel/鞋跟/细跟,粗跟；height/鞋帮/浅口,高帮 | 尖头→尖头，default 圆头；细跟→细跟，default 粗跟；浅口→浅口，default 高帮 |

**箱包（bags）公共属性**

| key | label | options | filterable |
|---|---|---|---|
| color | 颜色 | 黑色/棕色/卡其/灰色/藏青/米白/酒红/绿色/驼色 | true |
| material | 材质 | ABS/PU/尼龙/帆布/皮革/聚碳酸酯/聚酯纤维/铝框 | true |
| style | 风格 | 休闲/商务/基础/复古/旅行/正式/购物/运动/通勤 | true |
| gender | 适用性别 | 男/女/中性 | true |
| size | 尺码 | 小号/中号/大号/短款/长款/20寸/24寸/28寸/均码 | true |
| key_features | 设计细节 | tags | false |

箱包叶子：

| 叶子 | 可筛选属性 | 规则 |
|---|---|---|
| 双肩包 | capacity/容量/大容量,常规；closure/闭合/拉链,磁扣；laptop_sleeve/电脑夹层/有,无 | 大容量→大容量，default 常规；拉链主袋→拉链，default 磁扣；电脑夹层→有，default 无 |
| 手提包 | shape/包型/定型,软身；strap/肩带/可拆卸,固定；closure/闭合/拉链,磁扣 | 定型包身→定型，default 软身；可拆卸肩带→可拆卸，default 固定；拉链→拉链，default 磁扣 |
| 单肩包 | strap/肩带/可调节,固定；closure/闭合/磁扣,拉链；capacity/容量/轻量,大容量 | 可调节肩带→可调节，default 固定；磁扣→磁扣，default 拉链；轻量→轻量，default 大容量 |
| 斜挎包 | size/尺寸/小号,中号；closure/闭合/拉链,磁扣；front_pocket/前置口袋/有,无 | 小号→小号，default 中号；拉链→拉链，default 磁扣；前置口袋→有，default 无 |
| 钱包 | style/款式/对折,长款；rfid/RFID/有,无；capacity/容量/轻薄,多卡位 | 对折→对折，default 长款；RFID→有，default 无；轻薄→轻薄、卡位→多卡位，default 多卡位 |
| 行李箱 | size/尺寸/20寸,24寸,28寸；wheel/轮型/万向轮,静音轮；lock/锁具/TSA锁,普通锁 | 20寸→20寸，default 24寸；万向轮→万向轮、静音轮→静音轮，default 万向轮；TSA锁→TSA锁，default 普通锁 |
| 托特包 | capacity/容量/大容量,常规；closure/闭合/开口,拉链；carry_style/提法/肩带,手提 | 大容量→大容量，default 常规；开口→开口，default 拉链；肩带→肩带，default 手提 |
| 腰包 | closure/闭合/搭扣,拉链；capacity/容量/多隔层,轻量；waterproof/防水/防泼水,普通 | 搭扣→搭扣，default 拉链；多隔层→多隔层、轻量→轻量，default 轻量；防泼水→防泼水，default 普通 |

**配饰（accessories）公共属性**

| key | label | options | filterable |
|---|---|---|---|
| color | 颜色 | 黑色/白色/米白/灰色/棕色/卡其/红色/酒红/藏青/绿色 | true |
| material | 材质 | 925银/PU/TR90/不锈钢/合金/帆布/板材/棉/棉混纺/涤纶/皮革/真丝/硅胶/纯棉/绒面/羊毛/羊绒混纺/草编/金属/针织/钛钢 | true |
| style | 风格 | 休闲/复古/度假/户外/正式/运动/通勤 | true |
| gender | 适用性别 | 男/女/中性 | true |
| size | 尺码 | S/M/L/XL/均码 | true |
| key_features | 设计细节 | tags | false |

配饰叶子：

| 叶子 | 可筛选属性 | 规则 |
|---|---|---|
| 帽子 | adjustable/调节/可调节,固定；brim/帽檐/弯檐,平檐 | 可调节后扣→可调节，default 固定；弯檐→弯檐，default 平檐 |
| 围巾 | length/长度/长款,短款；pattern/图案/格纹,纯色；fringe/流苏/有,无 | 长款→长款，default 短款；格纹→格纹，default 纯色；流苏→有，default 无 |
| 腰带 | width/宽度/宽3.5cm,窄版；buckle/扣型/针扣,自动扣 | 宽3.5cm→宽3.5cm，default 窄版；针扣→针扣，default 自动扣 |
| 袜子 | length/长度/中筒,短筒；pattern/图案/纯色,条纹；cushion/加厚/加厚,常规 | 中筒→中筒，default 短筒；纯色→纯色，default 条纹；加厚→加厚，default 常规 |
| 手套 | fingers/分指/分指,连指；touchscreen/触屏/支持,不支持；lining/内里/加绒,常规 | 分指→分指，default 连指；触屏→支持，default 不支持；加绒→加绒，default 常规 |
| 墨镜 | frame/镜框/全框,半框；lens/镜片/偏光,普通；protection/防护/UV400,普通 | 全框→全框，default 半框；偏光→偏光，default 普通；UV400→UV400，default 普通 |
| 项链 | length/长度/锁骨链,长链；pendant/吊坠/有,无；chain/链条/细链,粗链 | 锁骨链→锁骨链，default 长链；吊坠→有，default 无；细链→细链，default 粗链 |
| 手表 | dial/表盘/圆形,方形；water_resistance/防水/30米,普通；movement/机芯/石英,机械 | 圆形表盘→圆形，default 方形；30米防水→30米，default 普通；石英机芯→石英，default 机械 |

> 说明：可筛选属性是“检索派生值”，由 `attribute_rules` 生成；`key_features` 始终保留 CSV 原始 token，详情页展示原始设计细节。颜色、品类、材质三项严格来自 CSV，不推断。

### 3.3 尺码与 SKU 规则

| 类别 | 尺码 |
|---|---|
| 服装（全部叶子） | S / M / L / XL / XXL（5 码） |
| 鞋靴，gender=女 | 35 / 36 / 37 / 38 / 39（5 码） |
| 鞋靴，gender=男/中性 | 39 / 40 / 41 / 42 / 43（5 码） |
| 双肩包/手提包/单肩包/斜挎包/托特包 | 小号 / 中号 / 大号（3 码） |
| 钱包 | 短款 / 长款（2 码） |
| 行李箱 | 20寸 / 24寸 / 28寸（3 码） |
| 腰包 | 均码（1 码） |
| 帽子/围巾/墨镜/项链/手表 | 均码（1 码） |
| 腰带/手套 | S / M / L / XL（4 码） |
| 袜子 | S / M / L（3 码） |

SKU 总数：

```text
服装 75 × 5 = 375
鞋靴 75 × 5 = 375
箱包 15×3 + 12×3 + 12×3 + 10×3 + 8×2 + 8×3 + 6×3 + 4×1 = 209
配饰 15×1 + 12×1 + 10×4 + 10×3 + 8×4 + 8×1 + 6×1 + 6×1 = 149
合计 375 + 375 + 209 + 149 = 1108
```

### 3.4 种子 JSON 结构

`backend/seeds/catalog/categories.json`：

```json
{
  "version": 1,
  "categories": [
    {
      "slug": "clothing",
      "name": "服装",
      "parent_slug": null,
      "level": 1,
      "sort_order": 1,
      "attribute_schema": {"attributes": [{"key": "color", "label": "颜色", "type": "enum", "options": ["黑色"], "filterable": true}]},
      "size_chart_template": {"type": "clothing", "unit": "cm", "rows": [{"size": "S", "height": [155, 165], "weight": [45, 55], "chest": [82, 88], "waist": [68, 74]}]}
    },
    {
      "slug": "shirts",
      "name": "衬衫",
      "parent_slug": "clothing",
      "level": 2,
      "sort_order": 1,
      "attribute_schema": {"attributes": [{"key": "collar_type", "label": "领型", "type": "enum", "options": ["翻领", "立领"], "filterable": true}]},
      "attribute_rules": {"collar_type": {"tokens": {"翻领": "翻领"}, "default": "立领"}},
      "size_chart_template": null
    }
  ]
}
```

`backend/seeds/catalog/products.json`：

```json
{
  "version": 1,
  "generated_from": "tools/image-batch/data/*.csv",
  "products": [
    {
      "product_code": "C001",
      "category_slug": "shirts",
      "title": "黑色纯棉翻领衬衫",
      "description": "黑色纯棉翻领衬衫。纯棉材质，常规版型，薄款，休闲风格，适用性别：男。设计细节：翻领、单排扣、左胸口袋。",
      "brand": "慕言 MUYAN",
      "price": 199.0,
      "original_price": 259.0,
      "main_image": "/static/products/C001_黑色.png",
      "images": ["/static/products/C001_黑色.png"],
      "attributes": {
        "color": "黑色",
        "material": "纯棉",
        "fit": "常规",
        "thickness": "薄款",
        "style": "休闲",
        "gender": "男",
        "season": ["春", "秋"],
        "size": ["S", "M", "L", "XL", "XXL"],
        "key_features": ["翻领", "单排扣", "左胸口袋"],
        "collar_type": "翻领",
        "sleeve_length": "长袖",
        "pattern": "纯色"
      },
      "size_chart": {"type": "clothing", "unit": "cm", "rows": [{"size": "S", "height": [155, 165], "weight": [45, 55], "chest": [82, 88], "waist": [68, 74]}]},
      "status": "on_sale",
      "sales_count": 320,
      "skus": [
        {"color": "黑色", "size": "S", "stock": 12, "sku_code": "C001-黑色-S", "price_override": null},
        {"color": "黑色", "size": "M", "stock": 8, "sku_code": "C001-黑色-M", "price_override": null}
      ]
    }
  ]
}
```

### 3.5 种子两步流程

```bash
# 只在 CSV / 品类 schema 变更、且确认要重新生成时执行
python -m scripts.build_catalog_seed --force

# 日常导入/重置后执行；JSON 有改动也可直接执行
python -m scripts.seed_catalog
```

- `build_catalog_seed.py` 默认拒绝覆盖已存在的 `products.json`，避免把人工修改冲掉。
- `seed_catalog.py` 只读取 JSON 中的价格、销量、库存、属性、SKU，不运行任何哈希/随机逻辑。
- `seed_catalog.py` 按 `categories.slug`、`products.product_code`、`product_skus.sku_code` upsert；商品 id 与收藏关系保持稳定。

---

## 4. 实施任务

### Task 1: 先更新设计文档契约

**Files:**
- Modify: `docs/superpowers/specs/2026-11-11-ai-shopping-agent-design.md` §7.2.2、§8.1、§8.2、§10.2

- [ ] **Step 1: 在 §7.2.2 的 products 表增加 product_code**

在 `id` 行后插入：

```markdown
| product_code | VARCHAR(20) UNIQUE NOT NULL | 商品编码，如 C001/S001/B001/A001 |
```

- [ ] **Step 2: 改写 §8.2 商品与 SKU 数据**

把原来的四条 bullet 替换为：

```markdown
- 总量约 300 个商品，4 个一级品类各 75 个。
- 一商品一图一色：每个商品只有 1 张主图和 1 个颜色，严格对应 `backend/static/products/{product_code}_{color}.png`；不生成无图颜色。
- 服装/鞋靴每商品 5 个尺码；箱包/配饰按实际 1~4 个尺寸，单尺码商品用“均码”并隐藏尺码选择。
- 当前种子实际 SKU 约 1100 条（服装 375、鞋靴 375、箱包 209、配饰 149），不再按 3000~5000 估算。
- 商品属性必须与图片严格一致（颜色、品类、材质）；`key_feature` 作为 `key_features` tags 展示，叶子 schema 只保留 2~3 个可筛选属性。
- 种子数据用 JSON 文件维护，脚本导入；SKU 由脚本按商品配置批量生成，库存随机 0~50。
- 每个服装/鞋靴商品配一份 `size_chart`；服装用身高/体重/胸围/腰围，鞋靴用脚长/欧码。
```

- [ ] **Step 3: 在 §8.1 末尾补充叶子 schema 规则**

在“后端合并规则”后追加：

```markdown
- 34 个叶子 schema 以 `backend/seeds/catalog/categories.json` 为准；一级品类提供公共属性，叶子只扩展 2~3 个可筛选属性；`key_features` 为展示用 tags，不参与筛选。
- 叶子可筛选属性的选项来自真实 CSV token 与每叶默认值，禁止把每个 `key_feature` token 都做成独立枚举。
```

- [ ] **Step 4: 在 §10.2 的接口列表后补充 DTO 约定**

```markdown
- 列表分页返回 `{items, total, page, page_size}`。
- `sort` 仅支持 `recommended | price_asc | price_desc`，默认 `recommended`（销量降序）。
- `category_id` 传一级品类时默认包含其全部叶子品类。
- `GET /api/products/{id}` 公开；带 Bearer 时返回 `is_favorited`。
- `POST/DELETE /api/products/{id}/favorite` 幂等，返回 `{favorited: bool}`。
- 收藏列表 `GET /api/favorites` 需要登录，返回商品摘要数组。
```

- [ ] **Step 5: 提交文档**

```bash
git add docs/superpowers/specs/2026-11-11-ai-shopping-agent-design.md
git commit -m "docs: pin M1 catalog contract"
```

---

### Task 2: 商品域 ORM 模型与 Alembic 迁移

**Files:**
- Create: `backend/app/modules/catalog/__init__.py`
- Create: `backend/app/modules/catalog/models.py`
- Modify: `backend/app/models.py`
- Modify: `backend/requirements.txt`
- Create: `backend/alembic/versions/20261113_0002_create_catalog.py`
- Test: `backend/tests/test_catalog_schema.py`

- [ ] **Step 1: 写失败的 schema 测试**

`backend/tests/test_catalog_schema.py`：

```python
import asyncio
import os

import asyncpg


def fetch_schema():
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

    async def _fetch():
        connection = await asyncpg.connect(dsn)
        try:
            extensions = await connection.fetch(
                "SELECT extname FROM pg_extension WHERE extname = 'vector'"
            )
            columns = await connection.fetch(
                """
                SELECT table_name, column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name IN ('categories', 'products', 'product_skus', 'favorites')
                ORDER BY table_name, ordinal_position
                """
            )
            constraints = await connection.fetch(
                """
                SELECT conname, contype
                FROM pg_constraint
                WHERE conrelid::regclass::text IN
                      ('categories', 'products', 'product_skus', 'favorites')
                """
            )
            indexes = await connection.fetch(
                """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename IN ('categories', 'products', 'product_skus', 'favorites')
                """
            )
            return extensions, columns, constraints, indexes
        finally:
            await connection.close()

    return asyncio.run(_fetch())


def test_catalog_tables_have_required_columns(migrated_database):
    extensions, columns, constraints, indexes = fetch_schema()
    assert [row["extname"] for row in extensions] == ["vector"]

    by_table: dict[str, dict[str, tuple[str, str]]] = {}
    for row in columns:
        by_table.setdefault(row["table_name"], {})[row["column_name"]] = (
            row["data_type"],
            row["is_nullable"],
        )

    assert set(by_table) == {"categories", "products", "product_skus", "favorites"}
    assert by_table["products"]["product_code"] == ("character varying", "NO")
    assert by_table["products"]["embedding"] == ("USER-DEFINED", "YES")
    assert by_table["products"]["attributes"] == ("jsonb", "NO")
    assert by_table["product_skus"]["sku_code"] == ("character varying", "NO")
    assert by_table["favorites"]["user_id"] == ("bigint", "NO")

    constraint_names = {row["conname"] for row in constraints}
    assert "uq_products_product_code" in constraint_names
    assert "uq_product_skus_product_color_size" in constraint_names
    assert "uq_product_skus_sku_code" in constraint_names
    assert "uq_favorites_user_product" in constraint_names

    index_defs = {row["indexname"]: row["indexdef"] for row in indexes}
    assert "ix_products_category_id" in index_defs
    assert "ix_products_attributes_gin" in index_defs
    assert "ix_products_embedding_hnsw" in index_defs
    assert "ix_product_skus_product_id" in index_defs
    assert "ix_favorites_user_id" in index_defs
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /d/develop/graduation-project-new/backend
source .venv/Scripts/activate
python -m pytest tests/test_catalog_schema.py -v
```

Expected: FAIL，`categories` 等表不存在。

- [ ] **Step 3: 增加 pgvector 依赖并安装**

`backend/requirements.txt` 末尾追加：

```text
pgvector>=0.3.6
```

```bash
pip install -r requirements.txt
```

- [ ] **Step 4: 写 ORM 模型**

`backend/app/modules/catalog/__init__.py` 为空文件。

`backend/app/modules/catalog/models.py`：

```python
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_categories_slug"),
        CheckConstraint("level IN (1, 2)", name="level_valid"),
        Index("ix_categories_parent_id", "parent_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("categories.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    slug: Mapped[str] = mapped_column(String(50), nullable=False)
    level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    attribute_schema: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    size_chart_template: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    parent: Mapped[Category | None] = relationship(
        remote_side="Category.id", back_populates="children"
    )
    children: Mapped[list[Category]] = relationship(
        back_populates="parent", cascade="all, delete-orphan"
    )
    products: Mapped[list[Product]] = relationship(back_populates="category")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("product_code", name="uq_products_product_code"),
        Index("ix_products_category_id", "category_id"),
        Index("ix_products_attributes_gin", "attributes", postgresql_using="gin"),
        Index(
            "ix_products_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_code: Mapped[str] = mapped_column(String(20), nullable=False)
    category_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    brand: Mapped[str | None] = mapped_column(String(100))
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    original_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    main_image: Mapped[str | None] = mapped_column(String(500))
    images: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    attributes: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    size_chart: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="on_sale", server_default="on_sale"
    )
    sales_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    category: Mapped[Category] = relationship(back_populates="products")
    skus: Mapped[list[ProductSku]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    favorites: Mapped[list[Favorite]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class ProductSku(Base):
    __tablename__ = "product_skus"
    __table_args__ = (
        UniqueConstraint(
            "product_id", "color", "size", name="uq_product_skus_product_color_size"
        ),
        UniqueConstraint("sku_code", name="uq_product_skus_sku_code"),
        CheckConstraint("stock >= 0", name="stock_non_negative"),
        Index("ix_product_skus_product_id", "product_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    color: Mapped[str] = mapped_column(String(30), nullable=False)
    size: Mapped[str] = mapped_column(String(20), nullable=False)
    stock: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    price_override: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    sku_code: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", server_default="active"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    product: Mapped[Product] = relationship(back_populates="skus")


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_favorites_user_product"),
        Index("ix_favorites_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    product: Mapped[Product] = relationship(back_populates="favorites")
```

`backend/app/models.py` 改为：

```python
"""集中导入所有 ORM 模型，供 Alembic 发现元数据。"""

from app.modules.auth.models import User  # noqa: F401
from app.modules.catalog.models import (  # noqa: F401
    Category,
    Favorite,
    Product,
    ProductSku,
)

__all__ = ["User", "Category", "Product", "ProductSku", "Favorite"]
```

- [ ] **Step 5: 写 Alembic 迁移**

`backend/alembic/versions/20261113_0002_create_catalog.py`：

```python
"""create catalog tables

Revision ID: 20261113_0002
Revises: 20261113_0001
Create Date: 2026-11-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "20261113_0002"
down_revision: Union[str, None] = "20261113_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "categories",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("parent_id", sa.BigInteger(), nullable=True),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("slug", sa.String(length=50), nullable=False),
        sa.Column("level", sa.SmallInteger(), nullable=False),
        sa.Column(
            "attribute_schema",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "size_chart_template",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("level IN (1, 2)", name="ck_categories_level_valid"),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["categories.id"],
            name="fk_categories_parent_id_categories",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_categories"),
        sa.UniqueConstraint("slug", name="uq_categories_slug"),
    )
    op.create_index("ix_categories_parent_id", "categories", ["parent_id"])

    op.create_table(
        "products",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("product_code", sa.String(length=20), nullable=False),
        sa.Column("category_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("brand", sa.String(length=100), nullable=True),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("original_price", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("main_image", sa.String(length=500), nullable=True),
        sa.Column(
            "images",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "attributes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "size_chart",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "status", sa.String(length=20), server_default="on_sale", nullable=False
        ),
        sa.Column("sales_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name="fk_products_category_id_categories",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_products"),
        sa.UniqueConstraint("product_code", name="uq_products_product_code"),
    )
    op.create_index("ix_products_category_id", "products", ["category_id"])
    op.create_index(
        "ix_products_attributes_gin",
        "products",
        ["attributes"],
        postgresql_using="gin",
    )
    op.execute(
        "CREATE INDEX ix_products_embedding_hnsw ON products "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    op.create_table(
        "product_skus",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("color", sa.String(length=30), nullable=False),
        sa.Column("size", sa.String(length=20), nullable=False),
        sa.Column("stock", sa.Integer(), server_default="0", nullable=False),
        sa.Column("price_override", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("sku_code", sa.String(length=50), nullable=False),
        sa.Column(
            "status", sa.String(length=20), server_default="active", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("stock >= 0", name="ck_product_skus_stock_non_negative"),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_product_skus_product_id_products",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_product_skus"),
        sa.UniqueConstraint(
            "product_id",
            "color",
            "size",
            name="uq_product_skus_product_color_size",
        ),
        sa.UniqueConstraint("sku_code", name="uq_product_skus_sku_code"),
    )
    op.create_index("ix_product_skus_product_id", "product_skus", ["product_id"])

    op.create_table(
        "favorites",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_favorites_product_id_products",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_favorites_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_favorites"),
        sa.UniqueConstraint("user_id", "product_id", name="uq_favorites_user_product"),
    )
    op.create_index("ix_favorites_user_id", "favorites", ["user_id"])


def downgrade() -> None:
    op.drop_table("favorites")
    op.drop_table("product_skus")
    op.drop_table("products")
    op.drop_table("categories")
```

- [ ] **Step 6: 运行迁移与测试**

```bash
cd /d/develop/graduation-project-new/backend
source .venv/Scripts/activate
python -m alembic upgrade head
python -m pytest tests/test_catalog_schema.py tests/test_db_schema.py -v
```

Expected: PASS。若 `vector` 扩展未安装，先确认 Docker 镜像是 `pgvector/pgvector:pg16`。

- [ ] **Step 7: 提交**

```bash
git add backend/requirements.txt backend/app/models.py backend/app/modules/catalog backend/alembic/versions/20261113_0002_create_catalog.py backend/tests/test_catalog_schema.py
git commit -m "feat: add catalog tables and migration"
```

---

### Task 3: Catalog DTO 与可选登录依赖

**Files:**
- Create: `backend/app/modules/catalog/schemas.py`
- Modify: `backend/app/modules/auth/deps.py`
- Test: `backend/tests/unit/test_catalog_schemas.py`

- [ ] **Step 1: 写失败的 DTO/合并测试**

`backend/tests/unit/test_catalog_schemas.py`：

```python
from app.modules.catalog.schemas import AttributeSchema, ProductPage
from app.modules.catalog.service import merge_attribute_schema


def test_merge_attribute_schema_leaf_overrides_parent():
    parent = {
        "attributes": [
            {"key": "color", "label": "颜色", "type": "enum", "options": ["黑"], "filterable": True},
            {"key": "material", "label": "材质", "type": "enum", "options": ["棉"], "filterable": True},
        ]
    }
    leaf = {
        "attributes": [
            {"key": "material", "label": "材质", "type": "enum", "options": ["亚麻"], "filterable": True},
            {"key": "collar_type", "label": "领型", "type": "enum", "options": ["翻领"], "filterable": True},
        ]
    }
    merged = merge_attribute_schema(parent, leaf)
    assert [item["key"] for item in merged["attributes"]] == [
        "color",
        "material",
        "collar_type",
    ]
    assert merged["attributes"][1]["options"] == ["亚麻"]
    assert AttributeSchema.model_validate(merged).attributes[2].label == "领型"


def test_product_page_shape():
    page = ProductPage(items=[], total=0, page=1, page_size=20)
    assert page.model_dump() == {
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": 20,
    }
```

- [ ] **Step 2: 运行确认失败**

```bash
python -m pytest tests/unit/test_catalog_schemas.py -v
```

Expected: FAIL，`app.modules.catalog.schemas` 不存在。

- [ ] **Step 3: 写 DTO**

`backend/app/modules/catalog/schemas.py`：

```python
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

AttributeType = Literal["enum", "multi_enum", "tags", "string", "number"]
SortOption = Literal["recommended", "price_asc", "price_desc"]


class AttributeDef(BaseModel):
    key: str
    label: str
    type: AttributeType = "enum"
    options: list[str] | None = None
    filterable: bool = False


class AttributeSchema(BaseModel):
    attributes: list[AttributeDef] = Field(default_factory=list)


class SizeChartRow(BaseModel):
    size: str
    height: list[int] | None = None
    weight: list[int] | None = None
    chest: list[int] | None = None
    waist: list[int] | None = None
    foot_length: list[int] | None = None


class SizeChart(BaseModel):
    type: Literal["clothing", "shoes"]
    unit: str
    rows: list[SizeChartRow]


class CategoryNode(BaseModel):
    id: int
    parent_id: int | None
    name: str
    slug: str
    level: int
    sort_order: int
    attribute_schema: AttributeSchema
    size_chart_template: SizeChart | None = None
    children: list[CategoryNode] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ProductSummary(BaseModel):
    id: int
    product_code: str
    category_id: int
    title: str
    price: float
    original_price: float | None
    main_image: str | None
    brand: str | None
    sales_count: int

    model_config = ConfigDict(from_attributes=True)


class SkuOut(BaseModel):
    id: int
    color: str
    size: str
    stock: int
    price: float
    status: str


class ProductDetail(ProductSummary):
    description: str | None
    images: list[str]
    attributes: dict[str, Any]
    attribute_schema: AttributeSchema
    size_chart: SizeChart | None
    category_name: str
    parent_category_name: str | None
    skus: list[SkuOut]
    is_favorited: bool = False


class ProductPage(BaseModel):
    items: list[ProductSummary]
    total: int
    page: int
    page_size: int


class FavoriteState(BaseModel):
    favorited: bool


CategoryNode.model_rebuild()
```

- [ ] **Step 4: 增加可选登录依赖**

在 `backend/app/modules/auth/deps.py` 末尾追加：

```python
async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """公开接口的可选登录：无 token 或 token 无效时按未登录处理。"""
    if credentials is None:
        return None
    try:
        user_id = decode_access_token(credentials.credentials)
    except InvalidTokenError:
        return None
    return await db.get(User, user_id)
```

- [ ] **Step 5: 写合并函数占位实现**

`backend/app/modules/catalog/service.py` 先写：

```python
from __future__ import annotations

from typing import Any


def merge_attribute_schema(*schemas: dict[str, Any] | None) -> dict[str, Any]:
    """从父级到叶子合并 attributes，同 key 以叶子为准，保持插入顺序。"""
    merged: dict[str, dict[str, Any]] = {}
    for schema in schemas:
        if not schema:
            continue
        attributes = schema.get("attributes")
        if not isinstance(attributes, list):
            continue
        for attribute in attributes:
            if isinstance(attribute, dict) and attribute.get("key"):
                merged[str(attribute["key"])] = attribute
    return {"attributes": list(merged.values())}
```

- [ ] **Step 6: 运行测试**

```bash
python -m pytest tests/unit/test_catalog_schemas.py -v
```

Expected: PASS。

- [ ] **Step 7: 提交**

```bash
git add backend/app/modules/catalog/schemas.py backend/app/modules/catalog/service.py backend/app/modules/auth/deps.py backend/tests/unit/test_catalog_schemas.py
git commit -m "feat: add catalog DTOs and optional auth"
```

---

### Task 4: 品类树接口

**Files:**
- Modify: `backend/app/modules/catalog/service.py`
- Create: `backend/app/modules/catalog/router.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_catalog_api.py`

- [ ] **Step 1: 写失败的品类树测试**

`backend/tests/test_catalog_api.py` 先写：

```python
import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]


def seed_catalog() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "scripts.seed_catalog"],
        cwd=BACKEND_DIR,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr


def test_categories_tree_has_merged_schema(client, seeded_catalog):
    response = client.get("/api/categories")
    assert response.status_code == 200
    roots = response.json()
    assert [item["name"] for item in roots] == ["服装", "鞋靴", "箱包", "配饰"]
    assert all(len(item["children"]) >= 8 for item in roots)

    clothing = roots[0]
    shirts = next(item for item in clothing["children"] if item["name"] == "衬衫")
    keys = [item["key"] for item in shirts["attribute_schema"]["attributes"]]
    assert "color" in keys
    assert "material" in keys
    assert "collar_type" in keys
    assert "key_features" in keys
    assert shirts["size_chart_template"]["type"] == "clothing"
```

- [ ] **Step 2: 运行确认失败**

```bash
python -m pytest tests/test_catalog_api.py::test_categories_tree_has_merged_schema -v
```

Expected: FAIL，`/api/categories` 404。

- [ ] **Step 3: 在 service.py 增加树构建**

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.models import Category
from app.modules.catalog.schemas import CategoryNode


async def get_category_tree(db: AsyncSession) -> list[CategoryNode]:
    categories = (
        await db.scalars(
            select(Category).order_by(
                Category.level.asc(), Category.sort_order.asc(), Category.id.asc()
            )
        )
    ).all()
    by_id = {category.id: category for category in categories}
    nodes: dict[int, CategoryNode] = {}

    for category in categories:
        parent = by_id.get(category.parent_id) if category.parent_id else None
        merged = merge_attribute_schema(
            parent.attribute_schema if parent else None,
            category.attribute_schema,
        )
        size_chart = (
            category.size_chart_template
            or (parent.size_chart_template if parent else None)
        )
        nodes[category.id] = CategoryNode(
            id=category.id,
            parent_id=category.parent_id,
            name=category.name,
            slug=category.slug,
            level=category.level,
            sort_order=category.sort_order,
            attribute_schema=merged,
            size_chart_template=size_chart,
            children=[],
        )

    roots: list[CategoryNode] = []
    for category in categories:
        node = nodes[category.id]
        if category.parent_id and category.parent_id in nodes:
            nodes[category.parent_id].children.append(node)
        else:
            roots.append(node)
    return roots
```

- [ ] **Step 4: 写 router 并在 main.py 注册**

`backend/app/modules/catalog/router.py`：

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.catalog import service
from app.modules.catalog.schemas import CategoryNode

router = APIRouter(tags=["catalog"])


@router.get("/categories", response_model=list[CategoryNode])
async def list_categories(
    db: AsyncSession = Depends(get_db),
) -> list[CategoryNode]:
    """返回 4 个一级品类及其全部叶子，叶子 schema 已合并父级属性。"""
    return await service.get_category_tree(db)
```

`backend/app/main.py` 增加：

```python
from app.modules.catalog.router import router as catalog_router
```

并在 `app.include_router(auth_router, prefix=settings.api_prefix)` 后增加：

```python
app.include_router(catalog_router, prefix=settings.api_prefix)
```

- [ ] **Step 5: 增加测试 fixture**

`backend/tests/conftest.py` 增加：

```python
@pytest.fixture
def clean_catalog(migrated_database):
    """清空商品域四表；不影响 users。"""

    async def _clean() -> None:
        engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE TABLE favorites, product_skus, products, categories "
                    "RESTART IDENTITY CASCADE"
                )
            )
        await engine.dispose()

    asyncio.run(_clean())
    yield


@pytest.fixture
def seeded_catalog(clean_catalog):
    """导入已提交的商品种子 JSON。"""
    result = subprocess.run(
        [sys.executable, "-m", "scripts.seed_catalog"],
        cwd=BACKEND_DIR,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    yield
```

- [ ] **Step 6: 运行测试**

```bash
python -m pytest tests/test_catalog_api.py::test_categories_tree_has_merged_schema -v
```

Expected: PASS（前提是 Task 9/10 已经生成 `seeds/catalog/*.json` 并能导入；若此时尚未生成种子，先完成 Task 9/10 再回来跑）。

- [ ] **Step 7: 提交**

```bash
git add backend/app/modules/catalog/service.py backend/app/modules/catalog/router.py backend/app/main.py backend/tests/conftest.py backend/tests/test_catalog_api.py
git commit -m "feat: add category tree API"
```

---

### Task 5: 商品列表接口

**Files:**
- Modify: `backend/app/modules/catalog/service.py`
- Modify: `backend/app/modules/catalog/router.py`
- Test: `backend/tests/test_catalog_api.py`

- [ ] **Step 1: 追加失败测试**

在 `backend/tests/test_catalog_api.py` 追加：

```python
def test_products_pagination_and_parent_category_include_children(
    client, seeded_catalog
):
    roots = client.get("/api/categories").json()
    clothing_id = roots[0]["id"]
    shirts_id = next(
        item["id"] for item in roots[0]["children"] if item["name"] == "衬衫"
    )

    page = client.get("/api/products?page=1&page_size=10").json()
    assert page["total"] == 300
    assert page["page"] == 1
    assert page["page_size"] == 10
    assert len(page["items"]) == 10

    by_parent = client.get(f"/api/products?category_id={clothing_id}&page_size=100").json()
    assert by_parent["total"] == 75

    by_leaf = client.get(f"/api/products?category_id={shirts_id}&page_size=100").json()
    assert by_leaf["total"] == 10
    assert all(item["category_id"] == shirts_id for item in by_leaf["items"])


def test_products_search_and_sort(client, seeded_catalog):
    search = client.get("/api/products?q=衬衫&page_size=100").json()
    assert search["total"] > 0
    assert all("衬衫" in item["title"] for item in search["items"])

    empty = client.get("/api/products?q=不存在的商品").json()
    assert empty["total"] == 0
    assert empty["items"] == []

    price_asc = client.get("/api/products?sort=price_asc&page_size=100").json()
    prices = [item["price"] for item in price_asc["items"]]
    assert prices == sorted(prices)

    price_desc = client.get("/api/products?sort=price_desc&page_size=100").json()
    prices = [item["price"] for item in price_desc["items"]]
    assert prices == sorted(prices, reverse=True)

    recommended = client.get("/api/products?sort=recommended&page_size=100").json()
    sales = [item["sales_count"] for item in recommended["items"]]
    assert sales == sorted(sales, reverse=True)

    invalid_sort = client.get("/api/products?sort=unknown")
    assert invalid_sort.status_code == 422


def test_products_unknown_category_returns_404(client, seeded_catalog):
    response = client.get("/api/products?category_id=999999")
    assert response.status_code == 404
```

- [ ] **Step 2: 运行确认失败**

```bash
python -m pytest tests/test_catalog_api.py -k "products" -v
```

Expected: FAIL，`/api/products` 404。

- [ ] **Step 3: 在 service.py 增加列表查询**

```python
from fastapi import HTTPException, status
from sqlalchemy import func, or_

from app.modules.catalog.models import Product
from app.modules.catalog.schemas import ProductPage, ProductSummary, SortOption


async def list_products(
    db: AsyncSession,
    *,
    category_id: int | None,
    q: str | None,
    page: int,
    page_size: int,
    sort: SortOption,
) -> ProductPage:
    filters = [Product.status == "on_sale"]

    if category_id is not None:
        category = await db.get(Category, category_id)
        if category is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="品类不存在"
            )
        if category.level == 1:
            child_ids = (
                await db.scalars(select(Category.id).where(Category.parent_id == category.id))
            ).all()
            filters.append(Product.category_id.in_(child_ids))
        else:
            filters.append(Product.category_id == category.id)

    keyword = (q or "").strip()
    if keyword:
        filters.append(
            or_(
                Product.title.contains(keyword, autoescape=True),
                Product.brand.contains(keyword, autoescape=True),
                Product.description.contains(keyword, autoescape=True),
            )
        )

    count_stmt = select(func.count()).select_from(Product).where(*filters)
    total = int(await db.scalar(count_stmt) or 0)

    order_by = {
        "recommended": (Product.sales_count.desc(), Product.id.asc()),
        "price_asc": (Product.price.asc(), Product.id.asc()),
        "price_desc": (Product.price.desc(), Product.id.asc()),
    }[sort]

    stmt = (
        select(Product)
        .where(*filters)
        .order_by(*order_by)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    products = (await db.scalars(stmt)).all()
    return ProductPage(
        items=[ProductSummary.model_validate(product) for product in products],
        total=total,
        page=page,
        page_size=page_size,
    )
```

- [ ] **Step 4: 在 router.py 增加端点**

```python
from fastapi import Query

from app.modules.catalog.schemas import ProductPage, SortOption


@router.get("/products", response_model=ProductPage)
async def list_products(
    category_id: int | None = None,
    q: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    sort: SortOption = "recommended",
    db: AsyncSession = Depends(get_db),
) -> ProductPage:
    """商品列表：公开；一级品类默认包含其全部叶子。"""
    return await service.list_products(
        db,
        category_id=category_id,
        q=q,
        page=page,
        page_size=page_size,
        sort=sort,
    )
```

- [ ] **Step 5: 运行测试**

```bash
python -m pytest tests/test_catalog_api.py -k "products" -v
```

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add backend/app/modules/catalog/service.py backend/app/modules/catalog/router.py backend/tests/test_catalog_api.py
git commit -m "feat: add product list API"
```

---

### Task 6: 商品详情接口

**Files:**
- Modify: `backend/app/modules/catalog/service.py`
- Modify: `backend/app/modules/catalog/router.py`
- Test: `backend/tests/test_catalog_api.py`

- [ ] **Step 1: 追加失败测试**

```python
def login(client, username: str = "catalog_user") -> str:
    client.post(
        "/api/auth/register",
        json={"username": username, "password": "secret123", "nickname": "测试"},
    )
    response = client.post(
        "/api/auth/login", json={"username": username, "password": "secret123"}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def first_product(client) -> dict:
    return client.get("/api/products?page_size=1").json()["items"][0]


def test_product_detail_is_public_and_contains_skus_and_size_chart(
    client, seeded_catalog
):
    product = first_product(client)
    response = client.get(f"/api/products/{product['id']}")
    assert response.status_code == 200
    detail = response.json()
    assert detail["id"] == product["id"]
    assert detail["product_code"] == product["product_code"]
    assert detail["is_favorited"] is False
    assert len(detail["skus"]) >= 1
    assert detail["attribute_schema"]["attributes"]
    assert "key_features" in detail["attributes"]
    assert detail["size_chart"]["type"] in {"clothing", "shoes"}
    assert detail["images"] == [detail["main_image"]]


def test_product_detail_invalid_token_is_treated_as_anonymous(
    client, seeded_catalog
):
    product = first_product(client)
    response = client.get(
        f"/api/products/{product['id']}",
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert response.status_code == 200
    assert response.json()["is_favorited"] is False


def test_product_detail_returns_is_favorited_when_logged_in(
    client, seeded_catalog
):
    token = login(client)
    product = first_product(client)
    headers = {"Authorization": f"Bearer {token}"}
    client.post(f"/api/products/{product['id']}/favorite", headers=headers)
    detail = client.get(f"/api/products/{product['id']}", headers=headers).json()
    assert detail["is_favorited"] is True


def test_product_detail_missing_returns_404(client, seeded_catalog):
    assert client.get("/api/products/999999").status_code == 404
```

- [ ] **Step 2: 运行确认失败**

```bash
python -m pytest tests/test_catalog_api.py -k "detail" -v
```

Expected: FAIL，详情端点 404（或收藏端点未实现）。

- [ ] **Step 3: 在 service.py 增加详情查询**

```python
from app.modules.catalog.models import Favorite, ProductSku
from app.modules.catalog.schemas import (
    AttributeSchema,
    ProductDetail,
    SkuOut,
)
from app.modules.auth.models import User


async def get_product_detail(
    db: AsyncSession, product_id: int, current_user: User | None
) -> ProductDetail:
    product = await db.scalar(
        select(Product).where(
            Product.id == product_id, Product.status == "on_sale"
        )
    )
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在或已下架"
        )

    category = await db.get(Category, product.category_id)
    parent = (
        await db.get(Category, category.parent_id)
        if category is not None and category.parent_id is not None
        else None
    )
    merged = merge_attribute_schema(
        parent.attribute_schema if parent else None,
        category.attribute_schema if category else None,
    )
    size_chart = (
        product.size_chart
        or (category.size_chart_template if category else None)
        or (parent.size_chart_template if parent else None)
    )

    skus = (
        await db.scalars(
            select(ProductSku)
            .where(
                ProductSku.product_id == product.id,
                ProductSku.status == "active",
            )
            .order_by(ProductSku.id.asc())
        )
    ).all()

    is_favorited = False
    if current_user is not None:
        is_favorited = (
            await db.scalar(
                select(Favorite.id).where(
                    Favorite.user_id == current_user.id,
                    Favorite.product_id == product.id,
                )
            )
        ) is not None

    images = list(product.images or [])
    if not images and product.main_image:
        images = [product.main_image]

    return ProductDetail(
        id=product.id,
        product_code=product.product_code,
        category_id=product.category_id,
        title=product.title,
        price=float(product.price),
        original_price=(
            float(product.original_price) if product.original_price is not None else None
        ),
        main_image=product.main_image,
        brand=product.brand,
        sales_count=product.sales_count,
        description=product.description,
        images=images,
        attributes=dict(product.attributes or {}),
        attribute_schema=AttributeSchema.model_validate(merged),
        size_chart=size_chart,
        category_name=category.name if category else "",
        parent_category_name=parent.name if parent else None,
        skus=[
            SkuOut(
                id=sku.id,
                color=sku.color,
                size=sku.size,
                stock=sku.stock,
                price=float(
                    sku.price_override
                    if sku.price_override is not None
                    else product.price
                ),
                status=sku.status,
            )
            for sku in skus
        ],
        is_favorited=is_favorited,
    )
```

- [ ] **Step 4: 在 router.py 增加端点**

```python
from app.modules.auth.deps import get_current_user_optional
from app.modules.auth.models import User
from app.modules.catalog.schemas import ProductDetail


@router.get("/products/{product_id}", response_model=ProductDetail)
async def get_product_detail(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
) -> ProductDetail:
    """商品详情：公开；带有效 Bearer 时返回 is_favorited。"""
    return await service.get_product_detail(db, product_id, current_user)
```

- [ ] **Step 5: 运行测试**

```bash
python -m pytest tests/test_catalog_api.py -k "detail" -v
```

Expected: PASS（收藏相关断言在 Task 7 实现后完整通过）。

- [ ] **Step 6: 提交**

```bash
git add backend/app/modules/catalog/service.py backend/app/modules/catalog/router.py backend/tests/test_catalog_api.py
git commit -m "feat: add product detail API"
```

---

### Task 7: 收藏接口

**Files:**
- Modify: `backend/app/modules/catalog/service.py`
- Modify: `backend/app/modules/catalog/router.py`
- Test: `backend/tests/test_catalog_api.py`

- [ ] **Step 1: 追加失败测试**

```python
def test_favorites_require_login(client, seeded_catalog):
    assert client.get("/api/favorites").status_code == 401
    product = first_product(client)
    assert client.post(f"/api/products/{product['id']}/favorite").status_code == 401
    assert client.delete(f"/api/products/{product['id']}/favorite").status_code == 401


def test_favorites_add_delete_are_idempotent(client, seeded_catalog):
    token = login(client)
    headers = {"Authorization": f"Bearer {token}"}
    product = first_product(client)

    first = client.post(f"/api/products/{product['id']}/favorite", headers=headers)
    assert first.status_code == 200
    assert first.json() == {"favorited": True}

    second = client.post(f"/api/products/{product['id']}/favorite", headers=headers)
    assert second.status_code == 200
    assert second.json() == {"favorited": True}

    favorites = client.get("/api/favorites", headers=headers).json()
    assert [item["id"] for item in favorites] == [product["id"]]

    first_delete = client.delete(
        f"/api/products/{product['id']}/favorite", headers=headers
    )
    assert first_delete.status_code == 200
    assert first_delete.json() == {"favorited": False}

    second_delete = client.delete(
        f"/api/products/{product['id']}/favorite", headers=headers
    )
    assert second_delete.status_code == 200
    assert second_delete.json() == {"favorited": False}

    assert client.get("/api/favorites", headers=headers).json() == []


def test_favorite_missing_product_returns_404(client, seeded_catalog):
    token = login(client)
    headers = {"Authorization": f"Bearer {token}"}
    assert client.post("/api/products/999999/favorite", headers=headers).status_code == 404
    assert client.delete("/api/products/999999/favorite", headers=headers).status_code == 404
```

- [ ] **Step 2: 运行确认失败**

```bash
python -m pytest tests/test_catalog_api.py -k "favorite" -v
```

Expected: FAIL。

- [ ] **Step 3: 在 service.py 增加收藏逻辑**

```python
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

from app.modules.catalog.schemas import FavoriteState


async def list_favorites(db: AsyncSession, user: User) -> list[ProductSummary]:
    stmt = (
        select(Product)
        .join(Favorite, Favorite.product_id == Product.id)
        .where(Favorite.user_id == user.id, Product.status == "on_sale")
        .order_by(Favorite.created_at.desc(), Favorite.id.desc())
    )
    products = (await db.scalars(stmt)).all()
    return [ProductSummary.model_validate(product) for product in products]


async def add_favorite(db: AsyncSession, user: User, product_id: int) -> FavoriteState:
    product = await db.scalar(
        select(Product.id).where(
            Product.id == product_id, Product.status == "on_sale"
        )
    )
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在或已下架"
        )
    existing = await db.scalar(
        select(Favorite.id).where(
            Favorite.user_id == user.id, Favorite.product_id == product_id
        )
    )
    if existing is None:
        db.add(Favorite(user_id=user.id, product_id=product_id))
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
    return FavoriteState(favorited=True)


async def remove_favorite(
    db: AsyncSession, user: User, product_id: int
) -> FavoriteState:
    product = await db.scalar(
        select(Product.id).where(
            Product.id == product_id, Product.status == "on_sale"
        )
    )
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在或已下架"
        )
    await db.execute(
        delete(Favorite).where(
            Favorite.user_id == user.id, Favorite.product_id == product_id
        )
    )
    await db.commit()
    return FavoriteState(favorited=False)
```

- [ ] **Step 4: 在 router.py 增加端点**

```python
from app.modules.auth.deps import get_current_user
from app.modules.catalog.schemas import FavoriteState, ProductSummary


@router.get("/favorites", response_model=list[ProductSummary])
async def list_favorites(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ProductSummary]:
    """当前用户收藏列表，按收藏时间倒序。"""
    return await service.list_favorites(db, current_user)


@router.post("/products/{product_id}/favorite", response_model=FavoriteState)
async def add_favorite(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FavoriteState:
    """收藏商品；重复收藏幂等。"""
    return await service.add_favorite(db, current_user, product_id)


@router.delete("/products/{product_id}/favorite", response_model=FavoriteState)
async def remove_favorite(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FavoriteState:
    """取消收藏；未收藏时幂等返回 false。"""
    return await service.remove_favorite(db, current_user, product_id)
```

- [ ] **Step 5: 运行测试**

```bash
python -m pytest tests/test_catalog_api.py -v
```

Expected: PASS（种子 JSON 存在时）。

- [ ] **Step 6: 提交**

```bash
git add backend/app/modules/catalog/service.py backend/app/modules/catalog/router.py backend/tests/test_catalog_api.py
git commit -m "feat: add favorites API"
```

---

### Task 8: 静态图片挂载与 Vite 代理

**Files:**
- Modify: `backend/app/main.py`
- Modify: `frontend/vite.config.ts`
- Test: `backend/tests/test_catalog_api.py`

- [ ] **Step 1: 追加失败测试**

```python
def test_static_product_image_is_served(client, seeded_catalog):
    product = first_product(client)
    image_path = product["main_image"]
    assert image_path.startswith("/static/products/")
    response = client.get(image_path)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/")
```

- [ ] **Step 2: 运行确认失败**

```bash
python -m pytest tests/test_catalog_api.py::test_static_product_image_is_served -v
```

Expected: FAIL，404。

- [ ] **Step 3: 挂载静态目录**

`backend/app/main.py` 增加：

```python
from pathlib import Path

from fastapi.staticfiles import StaticFiles

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
```

在 `app = FastAPI(...)` 后增加：

```python
app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR, check_dir=False),
    name="static",
)
```

- [ ] **Step 4: Vite 代理 `/static`**

`frontend/vite.config.ts` 的 `proxy` 增加：

```ts
'/static': {
  target: 'http://127.0.0.1:8100',
  changeOrigin: true,
},
```

- [ ] **Step 5: 运行测试**

```bash
python -m pytest tests/test_catalog_api.py::test_static_product_image_is_served -v
```

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add backend/app/main.py frontend/vite.config.ts backend/tests/test_catalog_api.py
git commit -m "feat: serve product images"
```

---

### Task 9: 品类种子 JSON（4 个一级 + 34 个叶子）

**Files:**
- Create: `backend/seeds/catalog/categories.json`

- [ ] **Step 1: 按 §3.1、§3.2 写入 categories.json**

要求：

- 4 个一级品类：`clothing`（服装）、`footwear`（鞋靴）、`bags`（箱包）、`accessories`（配饰），`parent_slug=null`，`level=1`，`sort_order=1..4`。
- 34 个叶子：按 §3.2 的表格顺序和 slug 写入，`parent_slug` 指向对应一级品类，`level=2`，`sort_order` 在每个父级内从 1 开始。
- 每个一级品类写入公共 `attribute_schema`（color/material/fit/thickness/style/gender/season/size/key_features 中适用的字段）。
- 每个叶子写入 2~3 个可筛选属性，以及 `attribute_rules`。
- `clothing`、`footwear` 的 `size_chart_template` 写入完整模板；叶子 `size_chart_template=null`。
- 所有 `options` 使用 §3.2 表格中的值；`attribute_rules.tokens` 使用 CSV 真实 token。

服装尺码模板：

```json
{
  "type": "clothing",
  "unit": "cm",
  "rows": [
    {"size": "S", "height": [155, 165], "weight": [45, 55], "chest": [82, 88], "waist": [68, 74]},
    {"size": "M", "height": [165, 172], "weight": [55, 65], "chest": [88, 94], "waist": [74, 80]},
    {"size": "L", "height": [170, 178], "weight": [65, 75], "chest": [94, 100], "waist": [80, 86]},
    {"size": "XL", "height": [176, 184], "weight": [75, 85], "chest": [100, 106], "waist": [86, 92]},
    {"size": "XXL", "height": [182, 190], "weight": [85, 95], "chest": [106, 112], "waist": [92, 98]}
  ]
}
```

鞋靴尺码模板：

```json
{
  "type": "shoes",
  "unit": "mm",
  "rows": [
    {"size": "35", "foot_length": [220, 225]},
    {"size": "36", "foot_length": [225, 230]},
    {"size": "37", "foot_length": [230, 235]},
    {"size": "38", "foot_length": [235, 240]},
    {"size": "39", "foot_length": [240, 245]},
    {"size": "40", "foot_length": [245, 250]},
    {"size": "41", "foot_length": [250, 255]},
    {"size": "42", "foot_length": [255, 260]},
    {"size": "43", "foot_length": [260, 265]}
  ]
}
```

- [ ] **Step 2: 用脚本校验 JSON 结构**

```bash
cd /d/develop/graduation-project-new/backend
source .venv/Scripts/activate
python - <<'PY'
import json
from pathlib import Path

data = json.loads(Path("seeds/catalog/categories.json").read_text(encoding="utf-8"))
categories = data["categories"]
parents = [c for c in categories if c["level"] == 1]
leaves = [c for c in categories if c["level"] == 2]
assert len(parents) == 4, len(parents)
assert len(leaves) == 34, len(leaves)
slugs = {c["slug"] for c in categories}
assert len(slugs) == len(categories)
for leaf in leaves:
    assert leaf["parent_slug"] in {p["slug"] for p in parents}
    attrs = leaf["attribute_schema"]["attributes"]
    assert 2 <= len(attrs) <= 3, (leaf["slug"], len(attrs))
    assert all(attr["filterable"] for attr in attrs)
    for attr in attrs:
        assert attr["options"], (leaf["slug"], attr["key"])
print("categories.json OK", len(parents), len(leaves))
PY
```

Expected: `categories.json OK 4 34`。

- [ ] **Step 3: 提交**

```bash
git add backend/seeds/catalog/categories.json
git commit -m "data: add category seed schemas"
```

---

### Task 10: `build_catalog_seed.py`（CSV → JSON）

**Files:**
- Create: `backend/scripts/build_catalog_seed.py`
- Test: `backend/tests/unit/test_catalog_seed_build.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_catalog_seed_build.py`：

```python
from scripts.build_catalog_seed import (
    assign_leaf_attributes,
    build_products,
    deterministic_price,
    sizes_for,
)


def test_sizes_for_rules():
    assert sizes_for("clothing", "男", "衬衫") == ["S", "M", "L", "XL", "XXL"]
    assert sizes_for("footwear", "女", "高跟鞋") == ["35", "36", "37", "38", "39"]
    assert sizes_for("footwear", "男", "运动鞋") == ["39", "40", "41", "42", "43"]
    assert sizes_for("bags", "中性", "钱包") == ["短款", "长款"]
    assert sizes_for("bags", "中性", "腰包") == ["均码"]
    assert sizes_for("accessories", "女", "腰带") == ["S", "M", "L", "XL"]
    assert sizes_for("accessories", "中性", "墨镜") == ["均码"]


def test_price_is_deterministic_and_within_range():
    first = deterministic_price("C001", "clothing")
    second = deterministic_price("C001", "clothing")
    assert first == second
    assert first >= 99 and first <= 399
    assert first % 10 == 9


def test_assign_leaf_attributes_uses_token_and_default():
    leaf = {
        "slug": "shirts",
        "attribute_rules": {
            "collar_type": {"tokens": {"翻领": "翻领"}, "default": "立领"},
            "sleeve_length": {"tokens": {"短袖": "短袖"}, "default": "长袖"},
            "pattern": {"tokens": {"条纹": "条纹", "格纹": "格纹"}, "default": "纯色"},
        },
    }
    assert assign_leaf_attributes(leaf, "翻领、单排扣、左胸口袋") == {
        "collar_type": "翻领",
        "sleeve_length": "长袖",
        "pattern": "纯色",
    }


def test_build_products_returns_300_products_and_1108_skus():
    products = build_products()
    assert len(products) == 300
    assert sum(len(product["skus"]) for product in products) == 1108
    assert {product["product_code"][0] for product in products} == {"C", "S", "B", "A"}
    assert all(product["original_price"] >= product["price"] for product in products)
    assert all(product["images"] == [product["main_image"]] for product in products)
    assert all(product["attributes"]["key_features"] for product in products)
```

- [ ] **Step 2: 运行确认失败**

```bash
python -m pytest tests/unit/test_catalog_seed_build.py -v
```

Expected: FAIL，模块不存在。

- [ ] **Step 3: 写 build 脚本**

`backend/scripts/build_catalog_seed.py`：

```python
"""从 image-batch CSV 生成商品种子 JSON。

默认拒绝覆盖已存在的 products.json；确需重建时加 --force。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent
CATEGORY_FILE = BACKEND_DIR / "seeds" / "catalog" / "categories.json"
OUTPUT_FILE = BACKEND_DIR / "seeds" / "catalog" / "products.json"
CSV_DIR = REPO_DIR / "tools" / "image-batch" / "data"
IMAGE_DIR = BACKEND_DIR / "static" / "products"

CSV_FILES = ["服装.csv", "鞋靴.csv", "箱包.csv", "配饰.csv"]
PRICE_RANGES = {
    "clothing": (99, 399),
    "footwear": (129, 499),
    "bags": (89, 599),
    "accessories": (29, 299),
}
BRANDS = {
    "clothing": "慕言 MUYAN",
    "footwear": "行步 XINGBU",
    "bags": "远行 YUANXING",
    "accessories": "点注 DIANZHU",
}
PARENT_BY_NAME = {"服装": "clothing", "鞋靴": "footwear", "箱包": "bags", "配饰": "accessories"}
CLOTHING_SIZES = ["S", "M", "L", "XL", "XXL"]
BAG_SIZES = {
    "双肩包": ["小号", "中号", "大号"],
    "手提包": ["小号", "中号", "大号"],
    "单肩包": ["小号", "中号", "大号"],
    "斜挎包": ["小号", "中号", "大号"],
    "钱包": ["短款", "长款"],
    "行李箱": ["20寸", "24寸", "28寸"],
    "托特包": ["小号", "中号", "大号"],
    "腰包": ["均码"],
}
ACCESSORY_SIZES = {
    "帽子": ["均码"],
    "围巾": ["均码"],
    "腰带": ["S", "M", "L", "XL"],
    "袜子": ["S", "M", "L"],
    "手套": ["S", "M", "L", "XL"],
    "墨镜": ["均码"],
    "项链": ["均码"],
    "手表": ["均码"],
}


def load_categories() -> dict[str, Any]:
    return json.loads(CATEGORY_FILE.read_text(encoding="utf-8"))


def _seed_int(key: str) -> int:
    return int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:16], 16)


def deterministic_price(product_code: str, parent_slug: str) -> int:
    minimum, maximum = PRICE_RANGES[parent_slug]
    rng = random.Random(_seed_int(product_code))
    tens_min = minimum // 10
    tens_max = maximum // 10
    price = rng.randint(tens_min, tens_max) * 10 + 9
    if price > maximum:
        price -= 10
    return max(minimum, price)


def deterministic_original_price(product_code: str, price: int) -> float:
    rng = random.Random(_seed_int(f"{product_code}:original"))
    multiplier = rng.choice([1.2, 1.3, 1.4, 1.5])
    return round(price * multiplier, 2)


def deterministic_sales_count(product_code: str) -> int:
    return random.Random(_seed_int(f"{product_code}:sales")).randint(20, 800)


def deterministic_stock(sku_code: str) -> int:
    return random.Random(_seed_int(f"{sku_code}:stock")).randint(0, 50)


def sizes_for(parent_slug: str, gender: str, leaf_name: str) -> list[str]:
    if parent_slug == "clothing":
        return list(CLOTHING_SIZES)
    if parent_slug == "footwear":
        return ["35", "36", "37", "38", "39"] if gender == "女" else ["39", "40", "41", "42", "43"]
    if parent_slug == "bags":
        return list(BAG_SIZES[leaf_name])
    if parent_slug == "accessories":
        return list(ACCESSORY_SIZES[leaf_name])
    raise ValueError(parent_slug)


def assign_leaf_attributes(leaf: dict[str, Any], key_feature: str) -> dict[str, str]:
    tokens = [token.strip() for token in key_feature.split("、") if token.strip()]
    values: dict[str, str] = {}
    for key, rule in leaf.get("attribute_rules", {}).items():
        token_map = rule.get("tokens", {})
        value = rule["default"]
        for token in tokens:
            if token in token_map:
                value = token_map[token]
                break
        values[key] = value
    return values


def build_title(row: dict[str, str]) -> str:
    feature = row["key_feature"].split("、")[0]
    material = row["material"].split("+")[0]
    return f"{row['color']}{material}{feature}{row['subcategory']}"


def build_description(row: dict[str, str], title: str) -> str:
    if row["category"] == "服装":
        return (
            f"{title}。{row['material']}材质，{row['fit']}版型，{row['thickness']}，"
            f"{row['style']}风格，适用性别：{row['gender']}。"
            f"设计细节：{row['key_feature']}。"
        )
    if row["category"] == "鞋靴":
        return (
            f"{title}。{row['material']}鞋面，{row['style']}风格，"
            f"适用性别：{row['gender']}。设计细节：{row['key_feature']}。"
        )
    return (
        f"{title}。{row['material']}材质，{row['style']}风格，"
        f"适用性别：{row['gender']}。设计细节：{row['key_feature']}。"
    )


def season_for(row: dict[str, str]) -> list[str]:
    if row["category"] != "服装":
        return []
    if row["thickness"] == "薄款":
        seasons = ["春", "夏"]
    elif row["thickness"] == "加厚":
        seasons = ["冬"]
    else:
        seasons = ["春", "秋"]
    if row["style"] == "度假" and "夏" not in seasons:
        seasons.append("夏")
    if row["style"] == "户外":
        for season in ("春", "秋"):
            if season not in seasons:
                seasons.append(season)
    return seasons


def size_chart_for(
    categories_by_slug: dict[str, dict[str, Any]],
    parent_slug: str,
    sizes: list[str],
) -> dict[str, Any] | None:
    if parent_slug not in {"clothing", "footwear"}:
        return None
    template = categories_by_slug[parent_slug]["size_chart_template"]
    rows = [row for row in template["rows"] if row["size"] in sizes]
    return {"type": template["type"], "unit": template["unit"], "rows": rows}


def build_products() -> list[dict[str, Any]]:
    data = load_categories()
    categories_by_slug = {item["slug"]: item for item in data["categories"]}
    leaves_by_parent_name = {
        (categories_by_slug[item["parent_slug"]]["name"], item["name"]): item
        for item in data["categories"]
        if item["level"] == 2
    }

    products: list[dict[str, Any]] = []
    missing_images: list[str] = []

    for csv_name in CSV_FILES:
        with (CSV_DIR / csv_name).open(encoding="utf-8-sig", newline="") as file:
            rows = list(csv.DictReader(file))
        for row in rows:
            product_code = row["id"]
            parent_slug = PARENT_BY_NAME[row["category"]]
            leaf = leaves_by_parent_name[(row["category"], row["subcategory"])]
            image_name = f"{product_code}_{row['color']}.png"
            if not (IMAGE_DIR / image_name).exists():
                missing_images.append(image_name)
            image_url = f"/static/products/{image_name}"

            sizes = sizes_for(parent_slug, row["gender"], row["subcategory"])
            leaf_attributes = assign_leaf_attributes(leaf, row["key_feature"])
            attributes: dict[str, Any] = {
                "color": row["color"],
                "material": row["material"],
                "style": row["style"],
                "gender": row["gender"],
                "size": sizes,
                "key_features": [
                    token.strip()
                    for token in row["key_feature"].split("、")
                    if token.strip()
                ],
                **leaf_attributes,
            }
            if parent_slug == "clothing":
                attributes["fit"] = row["fit"]
                attributes["thickness"] = row["thickness"]
                attributes["season"] = season_for(row)

            price = deterministic_price(product_code, parent_slug)
            original_price = deterministic_original_price(product_code, price)
            if original_price <= price:
                original_price = float(price + 10)
            skus = []
            for size in sizes:
                sku_code = f"{product_code}-{row['color']}-{size}"
                skus.append(
                    {
                        "color": row["color"],
                        "size": size,
                        "stock": deterministic_stock(sku_code),
                        "sku_code": sku_code,
                        "price_override": None,
                    }
                )

            products.append(
                {
                    "product_code": product_code,
                    "category_slug": leaf["slug"],
                    "title": build_title(row),
                    "description": build_description(row, build_title(row)),
                    "brand": BRANDS[parent_slug],
                    "price": float(price),
                    "original_price": float(original_price),
                    "main_image": image_url,
                    "images": [image_url],
                    "attributes": attributes,
                    "size_chart": size_chart_for(categories_by_slug, parent_slug, sizes),
                    "status": "on_sale",
                    "sales_count": deterministic_sales_count(product_code),
                    "skus": skus,
                }
            )

    if missing_images:
        raise SystemExit(
            "缺少商品图，请先补齐 backend/static/products：\n"
            + "\n".join(missing_images)
        )
    if len(products) != 300:
        raise SystemExit(f"商品数应为 300，实际 {len(products)}")
    total_skus = sum(len(product["skus"]) for product in products)
    if total_skus != 1108:
        raise SystemExit(f"SKU 数应为 1108，实际 {total_skus}")
    return products


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="覆盖已存在的 products.json")
    args = parser.parse_args()

    if OUTPUT_FILE.exists() and not args.force:
        print(f"{OUTPUT_FILE} 已存在，未覆盖；确需重建请加 --force")
        return

    products = build_products()
    OUTPUT_FILE.write_text(
        json.dumps(
            {
                "version": 1,
                "generated_from": "tools/image-batch/data/*.csv",
                "products": products,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    by_parent: dict[str, int] = {}
    for product in products:
        parent = product["category_slug"]
        by_parent[parent] = by_parent.get(parent, 0) + 1
    print(f"已生成 {OUTPUT_FILE}")
    print(f"商品：{len(products)}")
    print(f"SKU：{sum(len(product['skus']) for product in products)}")
    print(f"图片：{len(products)} 张校验通过")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行测试**

```bash
python -m pytest tests/unit/test_catalog_seed_build.py -v
```

Expected: PASS。

- [ ] **Step 5: 生成 JSON**

```bash
python -m scripts.build_catalog_seed
```

Expected:

```text
已生成 .../backend/seeds/catalog/products.json
商品：300
SKU：1108
图片：300 张校验通过
```

- [ ] **Step 6: 提交**

```bash
git add backend/scripts/build_catalog_seed.py backend/tests/unit/test_catalog_seed_build.py backend/seeds/catalog/products.json
git commit -m "data: build catalog seed from csv"
```

---

### Task 11: `seed_catalog.py`（JSON → DB upsert）

**Files:**
- Create: `backend/scripts/seed_catalog.py`
- Test: `backend/tests/test_catalog_seed.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_catalog_seed.py`：

```python
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import asyncpg

BACKEND_DIR = Path(__file__).resolve().parents[1]
CATEGORY_FILE = BACKEND_DIR / "seeds" / "catalog" / "categories.json"
PRODUCT_FILE = BACKEND_DIR / "seeds" / "catalog" / "products.json"


def run_seed() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "scripts.seed_catalog"],
        cwd=BACKEND_DIR,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def fetch_counts() -> dict[str, int]:
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

    async def _fetch():
        connection = await asyncpg.connect(dsn)
        try:
            return {
                "categories": await connection.fetchval("SELECT count(*) FROM categories"),
                "parents": await connection.fetchval(
                    "SELECT count(*) FROM categories WHERE level = 1"
                ),
                "leaves": await connection.fetchval(
                    "SELECT count(*) FROM categories WHERE level = 2"
                ),
                "products": await connection.fetchval("SELECT count(*) FROM products"),
                "skus": await connection.fetchval("SELECT count(*) FROM product_skus"),
            }
        finally:
            await connection.close()

    return asyncio.run(_fetch())


def test_seed_counts_and_image_files(clean_catalog):
    result = run_seed()
    assert result.returncode == 0, result.stderr
    assert "品类：4 个一级 + 34 个叶子" in result.stdout
    assert "商品：300" in result.stdout
    assert "SKU：1108" in result.stdout
    counts = fetch_counts()
    assert counts == {
        "categories": 38,
        "parents": 4,
        "leaves": 34,
        "products": 300,
        "skus": 1108,
    }

    data = json.loads(PRODUCT_FILE.read_text(encoding="utf-8"))
    products = data["products"]
    assert len(products) == 300
    assert all(product["original_price"] >= product["price"] for product in products)
    assert all(product["images"] == [product["main_image"]] for product in products)
    for product in products:
        image = BACKEND_DIR / product["main_image"].removeprefix("/static/")
        assert image.exists(), image


def test_seed_is_idempotent_and_keeps_favorites(client, clean_catalog):
    first = run_seed()
    assert first.returncode == 0, first.stderr

    client.post(
        "/api/auth/register",
        json={"username": "seed_user", "password": "secret123"},
    )
    token = client.post(
        "/api/auth/login",
        json={"username": "seed_user", "password": "secret123"},
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    product = client.get("/api/products?page_size=1").json()["items"][0]
    client.post(f"/api/products/{product['id']}/favorite", headers=headers)

    second = run_seed()
    assert second.returncode == 0, second.stderr
    counts = fetch_counts()
    assert counts["products"] == 300
    assert counts["skus"] == 1108
    favorites = client.get("/api/favorites", headers=headers).json()
    assert [item["id"] for item in favorites] == [product["id"]]


def test_seed_validates_images_and_counts(clean_catalog):
    data = json.loads(PRODUCT_FILE.read_text(encoding="utf-8"))
    assert len(data["products"]) == 300
    assert sum(len(product["skus"]) for product in data["products"]) == 1108
```

- [ ] **Step 2: 运行确认失败**

```bash
python -m pytest tests/test_catalog_seed.py -v
```

Expected: FAIL，模块不存在。

- [ ] **Step 3: 写 seed 脚本**

`backend/scripts/seed_catalog.py`：

```python
"""把 seeds/catalog/*.json 导入数据库；重复执行幂等。"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.session import AsyncSessionLocal, engine
from app.modules.catalog.models import Category, Product, ProductSku

BACKEND_DIR = Path(__file__).resolve().parents[1]
CATEGORY_FILE = BACKEND_DIR / "seeds" / "catalog" / "categories.json"
PRODUCT_FILE = BACKEND_DIR / "seeds" / "catalog" / "products.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(categories: list[dict[str, Any]], products: list[dict[str, Any]]) -> None:
    parents = [item for item in categories if item["level"] == 1]
    leaves = [item for item in categories if item["level"] == 2]
    if len(parents) != 4 or len(leaves) != 34:
        raise SystemExit(f"品类数错误：{len(parents)} 一级 / {len(leaves)} 叶子")

    slugs = [item["slug"] for item in categories]
    if len(set(slugs)) != len(slugs):
        raise SystemExit("品类 slug 重复")
    parent_slugs = {item["slug"] for item in parents}
    leaf_slugs = {item["slug"] for item in leaves}
    for leaf in leaves:
        if leaf["parent_slug"] not in parent_slugs:
            raise SystemExit(f"叶子父级不存在：{leaf['slug']}")

    if len(products) != 300:
        raise SystemExit(f"商品数应为 300，实际 {len(products)}")
    codes = [item["product_code"] for item in products]
    if len(set(codes)) != len(codes):
        raise SystemExit("product_code 重复")

    seen_image_names: set[str] = set()
    total_skus = 0
    for product in products:
        if product["category_slug"] not in leaf_slugs:
            raise SystemExit(f"商品品类不是叶子：{product['product_code']}")
        if product["original_price"] < product["price"]:
            raise SystemExit(f"original_price 小于 price：{product['product_code']}")
        image_path = BACKEND_DIR / product["main_image"].removeprefix("/static/")
        if not image_path.exists():
            raise SystemExit(f"商品图不存在：{image_path}")
        image_name = image_path.name
        if image_name in seen_image_names:
            raise SystemExit(f"商品图重复引用：{image_name}")
        seen_image_names.add(image_name)
        if not product["skus"]:
            raise SystemExit(f"商品没有 SKU：{product['product_code']}")
        if len(product["skus"]) != len(product["attributes"].get("size", [])):
            raise SystemExit(f"SKU 数与 size 不一致：{product['product_code']}")
        sku_codes = [sku["sku_code"] for sku in product["skus"]]
        if len(set(sku_codes)) != len(sku_codes):
            raise SystemExit(f"sku_code 重复：{product['product_code']}")
        total_skus += len(product["skus"])

    if total_skus != 1108:
        raise SystemExit(f"SKU 数应为 1108，实际 {total_skus}")
    if len(seen_image_names) != 300:
        raise SystemExit(f"图片数应为 300，实际 {len(seen_image_names)}")


async def upsert_categories(
    session, categories: list[dict[str, Any]]
) -> dict[str, int]:
    parents = [item for item in categories if item["level"] == 1]
    leaves = [item for item in categories if item["level"] == 2]
    ids: dict[str, int] = {}

    for item in parents:
        stmt = (
            pg_insert(Category)
            .values(
                slug=item["slug"],
                name=item["name"],
                parent_id=None,
                level=item["level"],
                attribute_schema=item["attribute_schema"],
                size_chart_template=item.get("size_chart_template"),
                sort_order=item.get("sort_order", 0),
            )
            .on_conflict_do_update(
                index_elements=[Category.slug],
                set_={
                    "name": item["name"],
                    "parent_id": None,
                    "level": item["level"],
                    "attribute_schema": item["attribute_schema"],
                    "size_chart_template": item.get("size_chart_template"),
                    "sort_order": item.get("sort_order", 0),
                    "updated_at": func.now(),
                },
            )
            .returning(Category.id)
        )
        ids[item["slug"]] = int(await session.scalar(stmt))

    for item in leaves:
        stmt = (
            pg_insert(Category)
            .values(
                slug=item["slug"],
                name=item["name"],
                parent_id=ids[item["parent_slug"]],
                level=item["level"],
                attribute_schema=item["attribute_schema"],
                size_chart_template=item.get("size_chart_template"),
                sort_order=item.get("sort_order", 0),
            )
            .on_conflict_do_update(
                index_elements=[Category.slug],
                set_={
                    "name": item["name"],
                    "parent_id": ids[item["parent_slug"]],
                    "level": item["level"],
                    "attribute_schema": item["attribute_schema"],
                    "size_chart_template": item.get("size_chart_template"),
                    "sort_order": item.get("sort_order", 0),
                    "updated_at": func.now(),
                },
            )
            .returning(Category.id)
        )
        ids[item["slug"]] = int(await session.scalar(stmt))

    return ids


async def upsert_products(
    session, products: list[dict[str, Any]], category_ids: dict[str, int]
) -> dict[str, int]:
    values = [
        {
            "product_code": product["product_code"],
            "category_id": category_ids[product["category_slug"]],
            "title": product["title"],
            "description": product["description"],
            "brand": product["brand"],
            "price": product["price"],
            "original_price": product["original_price"],
            "main_image": product["main_image"],
            "images": product["images"],
            "attributes": product["attributes"],
            "size_chart": product["size_chart"],
            "status": product["status"],
            "sales_count": product["sales_count"],
        }
        for product in products
    ]
    stmt = pg_insert(Product).values(values)
    excluded = stmt.excluded
    stmt = stmt.on_conflict_do_update(
        index_elements=[Product.product_code],
        set_={
            "category_id": excluded.category_id,
            "title": excluded.title,
            "description": excluded.description,
            "brand": excluded.brand,
            "price": excluded.price,
            "original_price": excluded.original_price,
            "main_image": excluded.main_image,
            "images": excluded.images,
            "attributes": excluded.attributes,
            "size_chart": excluded.size_chart,
            "status": excluded.status,
            "sales_count": excluded.sales_count,
            "updated_at": func.now(),
        },
    ).returning(Product.id, Product.product_code)
    rows = (await session.execute(stmt)).all()
    return {row.product_code: row.id for row in rows}


async def upsert_skus(
    session, products: list[dict[str, Any]], product_ids: dict[str, int]
) -> None:
    values = []
    all_sku_codes: list[str] = []
    for product in products:
        product_id = product_ids[product["product_code"]]
        for sku in product["skus"]:
            all_sku_codes.append(sku["sku_code"])
            values.append(
                {
                    "product_id": product_id,
                    "color": sku["color"],
                    "size": sku["size"],
                    "stock": sku["stock"],
                    "price_override": sku["price_override"],
                    "sku_code": sku["sku_code"],
                    "status": "active",
                }
            )
    stmt = pg_insert(ProductSku).values(values)
    excluded = stmt.excluded
    stmt = stmt.on_conflict_do_update(
        index_elements=[ProductSku.sku_code],
        set_={
            "product_id": excluded.product_id,
            "color": excluded.color,
            "size": excluded.size,
            "stock": excluded.stock,
            "price_override": excluded.price_override,
            "status": "active",
            "updated_at": func.now(),
        },
    )
    await session.execute(stmt)
    await session.execute(
        update(ProductSku)
        .where(
            ProductSku.product_id.in_(product_ids.values()),
            ProductSku.sku_code.notin_(all_sku_codes),
        )
        .values(status="inactive", updated_at=func.now())
    )


async def seed_catalog() -> None:
    category_data = load_json(CATEGORY_FILE)["categories"]
    product_data = load_json(PRODUCT_FILE)["products"]
    validate(category_data, product_data)

    async with AsyncSessionLocal() as session:
        category_ids = await upsert_categories(session, category_data)
        product_ids = await upsert_products(session, product_data, category_ids)
        await upsert_skus(session, product_data, product_ids)
        await session.commit()

    print(f"品类：4 个一级 + 34 个叶子")
    print(f"商品：{len(product_data)}")
    print(f"SKU：{sum(len(product['skus']) for product in product_data)}")
    print(f"图片：{len(product_data)} 张校验通过")


async def main() -> None:
    try:
        await seed_catalog()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: 运行导入与测试**

```bash
python -m scripts.seed_catalog
python -m pytest tests/test_catalog_seed.py tests/test_catalog_api.py -v
```

Expected: seed 输出 4/34/300/1108；pytest PASS。

- [ ] **Step 5: 再跑一次验证幂等**

```bash
python -m scripts.seed_catalog
```

Expected: 数量不变，无异常。

- [ ] **Step 6: 提交**

```bash
git add backend/scripts/seed_catalog.py backend/tests/test_catalog_seed.py
git commit -m "data: add idempotent catalog seed importer"
```

---

### Task 12: 前端类型、API 与 store

**Files:**
- Create: `frontend/src/types/catalog.ts`
- Create: `frontend/src/api/catalog.ts`
- Create: `frontend/src/stores/catalog.ts`
- Create: `frontend/src/stores/favorites.ts`
- Create: `frontend/src/utils/format.ts`
- Create: `frontend/src/utils/colors.ts`

- [ ] **Step 1: 写类型**

`frontend/src/types/catalog.ts`：

```ts
export interface AttributeDef {
  key: string
  label: string
  type: 'enum' | 'multi_enum' | 'tags' | 'string' | 'number'
  options?: string[] | null
  filterable: boolean
}

export interface AttributeSchema {
  attributes: AttributeDef[]
}

export interface SizeChartRow {
  size: string
  height?: number[]
  weight?: number[]
  chest?: number[]
  waist?: number[]
  foot_length?: number[]
}

export interface SizeChart {
  type: 'clothing' | 'shoes'
  unit: string
  rows: SizeChartRow[]
}

export interface Category {
  id: number
  parent_id: number | null
  name: string
  slug: string
  level: number
  sort_order: number
  attribute_schema: AttributeSchema
  size_chart_template: SizeChart | null
  children: Category[]
}

export interface ProductSummary {
  id: number
  product_code: string
  category_id: number
  title: string
  price: number
  original_price: number | null
  main_image: string | null
  brand: string | null
  sales_count: number
}

export interface ProductSku {
  id: number
  color: string
  size: string
  stock: number
  price: number
  status: string
}

export interface ProductDetail extends ProductSummary {
  description: string | null
  images: string[]
  attributes: Record<string, string | string[] | number>
  attribute_schema: AttributeSchema
  size_chart: SizeChart | null
  category_name: string
  parent_category_name: string | null
  skus: ProductSku[]
  is_favorited: boolean
}

export interface ProductPage {
  items: ProductSummary[]
  total: number
  page: number
  page_size: number
}

export interface FavoriteState {
  favorited: boolean
}

export type ProductSort = 'recommended' | 'price_asc' | 'price_desc'
```

- [ ] **Step 2: 写 API 封装**

`frontend/src/api/catalog.ts`：

```ts
import http from '@/api/http'
import type {
  Category,
  FavoriteState,
  ProductDetail,
  ProductPage,
  ProductSort,
  ProductSummary,
} from '@/types/catalog'

export interface ProductQuery {
  category_id?: number
  q?: string
  page?: number
  page_size?: number
  sort?: ProductSort
}

export async function fetchCategories(): Promise<Category[]> {
  const { data } = await http.get<Category[]>('/categories')
  return data
}

export async function fetchProducts(query: ProductQuery = {}): Promise<ProductPage> {
  const { data } = await http.get<ProductPage>('/products', { params: query })
  return data
}

export async function fetchProduct(id: number): Promise<ProductDetail> {
  const { data } = await http.get<ProductDetail>(`/products/${id}`)
  return data
}

export async function fetchFavorites(): Promise<ProductSummary[]> {
  const { data } = await http.get<ProductSummary[]>('/favorites')
  return data
}

export async function addFavorite(id: number): Promise<FavoriteState> {
  const { data } = await http.post<FavoriteState>(`/products/${id}/favorite`)
  return data
}

export async function removeFavorite(id: number): Promise<FavoriteState> {
  const { data } = await http.delete<FavoriteState>(`/products/${id}/favorite`)
  return data
}
```

- [ ] **Step 3: 写 catalog store**

`frontend/src/stores/catalog.ts`：

```ts
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { fetchCategories } from '@/api/catalog'
import type { Category } from '@/types/catalog'

export const useCatalogStore = defineStore('catalog', () => {
  const categories = ref<Category[]>([])
  const loading = ref(false)
  const loaded = ref(false)
  let pending: Promise<void> | null = null

  async function load(): Promise<void> {
    if (loaded.value) {
      return
    }
    if (pending) {
      return pending
    }
    loading.value = true
    pending = fetchCategories()
      .then((data) => {
        categories.value = data
        loaded.value = true
      })
      .finally(() => {
        loading.value = false
        pending = null
      })
    return pending
  }

  function find(id: number): Category | undefined {
    const walk = (items: Category[]): Category | undefined => {
      for (const item of items) {
        if (item.id === id) {
          return item
        }
        const found = walk(item.children)
        if (found) {
          return found
        }
      }
      return undefined
    }
    return walk(categories.value)
  }

  const roots = computed(() => categories.value)

  return { categories, roots, loading, loaded, load, find }
})
```

- [ ] **Step 4: 写 favorites store**

`frontend/src/stores/favorites.ts`：

```ts
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { addFavorite, fetchFavorites, removeFavorite } from '@/api/catalog'
import type { ProductSummary } from '@/types/catalog'

export const useFavoritesStore = defineStore('favorites', () => {
  const items = ref<ProductSummary[]>([])
  const loading = ref(false)
  const loaded = ref(false)
  let pending: Promise<void> | null = null

  const ids = computed(() => new Set(items.value.map((item) => item.id)))

  async function load(force = false): Promise<void> {
    if (loaded.value && !force) {
      return
    }
    if (pending && !force) {
      return pending
    }
    loading.value = true
    pending = fetchFavorites()
      .then((data) => {
        items.value = data
        loaded.value = true
      })
      .finally(() => {
        loading.value = false
        pending = null
      })
    return pending
  }

  function isFavorite(id: number): boolean {
    return ids.value.has(id)
  }

  async function toggle(product: ProductSummary): Promise<boolean> {
    const state = isFavorite(product.id)
      ? await removeFavorite(product.id)
      : await addFavorite(product.id)
    if (state.favorited) {
      if (!isFavorite(product.id)) {
        items.value = [product, ...items.value]
      }
    } else {
      items.value = items.value.filter((item) => item.id !== product.id)
    }
    loaded.value = true
    return state.favorited
  }

  function clear(): void {
    items.value = []
    loaded.value = false
  }

  return { items, loading, loaded, ids, load, isFavorite, toggle, clear }
})
```

- [ ] **Step 5: 写格式化工具**

`frontend/src/utils/format.ts`：

```ts
export function formatPrice(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(2)
}

export function formatRange(value?: number[] | null): string {
  if (!value || value.length === 0) {
    return '-'
  }
  return value.length === 1 ? String(value[0]) : `${value[0]}-${value[value.length - 1]}`
}

export function formatAttributeValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.join('、')
  }
  if (typeof value === 'string') {
    return value
  }
  if (typeof value === 'number') {
    return String(value)
  }
  return ''
}
```

`frontend/src/utils/colors.ts`：

```ts
export const COLOR_HEX: Record<string, string> = {
  黑色: '#111111',
  白色: '#F5F5F5',
  米白: '#EFE8DA',
  浅灰: '#C8C8C8',
  深灰: '#555555',
  灰色: '#8A8A8A',
  藏青: '#1F2A44',
  蓝色: '#2F5FAF',
  浅蓝: '#A8C4E0',
  卡其: '#C3B091',
  棕色: '#6B4A2F',
  绿色: '#3E6B4F',
  酒红: '#6E2639',
  驼色: '#B08D62',
  粉色: '#E8B4B8',
  黄色: '#D9A441',
  红色: '#C0392B',
}

export function colorHex(name: string): string {
  return COLOR_HEX[name] ?? '#D8DCE1'
}
```

- [ ] **Step 6: 运行构建**

```bash
cd /d/develop/graduation-project-new/frontend
npm run build
```

Expected: 构建通过（此时页面还未使用新 store，类型必须无报错）。

- [ ] **Step 7: 提交**

```bash
git add frontend/src/types/catalog.ts frontend/src/api/catalog.ts frontend/src/stores/catalog.ts frontend/src/stores/favorites.ts frontend/src/utils/format.ts frontend/src/utils/colors.ts
git commit -m "feat: add catalog frontend data layer"
```

---

### Task 13: 可复用商品发现组件与 AI 找货 Tab

**Files:**
- Create: `frontend/src/components/catalog/ProductImage.vue`
- Create: `frontend/src/components/catalog/ProductCard.vue`
- Create: `frontend/src/components/catalog/ProductDiscoveryPanel.vue`
- Modify: `frontend/src/views/user/HomeView.vue`

- [ ] **Step 1: 写 ProductImage**

```vue
<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  src: string | null
  alt: string
}>()

const failed = ref(false)

watch(
  () => props.src,
  () => {
    failed.value = false
  },
)
</script>

<template>
  <div class="product-image">
    <img
      v-if="src && !failed"
      :src="src"
      :alt="alt"
      loading="lazy"
      @error="failed = true"
    />
    <div v-else class="product-image-fallback">
      <span>{{ alt.slice(0, 1) }}</span>
    </div>
  </div>
</template>

<style scoped>
.product-image {
  width: 100%;
  aspect-ratio: 1 / 1;
  overflow: hidden;
  background: var(--color-field-bg);
}

.product-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.product-image-fallback {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #fff1e8, #ffd9c4);
  color: var(--color-primary);
  font-size: 24px;
  font-weight: 800;
}
</style>
```

- [ ] **Step 2: 写 ProductCard**

```vue
<script setup lang="ts">
import ProductImage from '@/components/catalog/ProductImage.vue'
import type { ProductSummary } from '@/types/catalog'
import { formatPrice } from '@/utils/format'

defineProps<{
  product: ProductSummary
}>()
</script>

<template>
  <router-link
    :to="{ name: 'product-detail', params: { id: product.id } }"
    class="product-card"
  >
    <ProductImage :src="product.main_image" :alt="product.title" />
    <div class="product-card-body">
      <div class="product-card-title">{{ product.title }}</div>
      <div class="product-card-meta">
        <span class="product-card-price"><small>¥</small>{{ formatPrice(product.price) }}</span>
        <span class="product-card-sales">已售 {{ product.sales_count }}</span>
      </div>
    </div>
  </router-link>
</template>

<style scoped>
.product-card {
  display: block;
  background: var(--color-card);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  overflow: hidden;
  color: inherit;
  text-decoration: none;
}

.product-card-body {
  padding: 8px 9px 10px;
}

.product-card-title {
  font-size: 12px;
  line-height: 1.35;
  font-weight: 600;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
  min-height: 32px;
}

.product-card-meta {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 6px;
  margin-top: 6px;
}

.product-card-price {
  color: var(--color-price);
  font-size: 15px;
  font-weight: 800;
}

.product-card-price small {
  font-size: 9px;
  margin-right: 1px;
}

.product-card-sales {
  font-size: 9px;
  color: var(--color-text-secondary);
  white-space: nowrap;
}
</style>
```

- [ ] **Step 3: 写 ProductDiscoveryPanel**

```vue
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { fetchProducts } from '@/api/catalog'
import ProductCard from '@/components/catalog/ProductCard.vue'
import { useCatalogStore } from '@/stores/catalog'
import type { ProductSummary } from '@/types/catalog'

const catalog = useCatalogStore()
const products = ref<ProductSummary[]>([])
const loading = ref(true)

const categories = computed(() => catalog.roots.slice(0, 4))

onMounted(async () => {
  try {
    await catalog.load()
    const page = await fetchProducts({ page_size: 8, sort: 'recommended' })
    products.value = page.items
  } catch {
    products.value = []
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <section class="discovery-panel">
    <div class="section-head">
      <h2>按品类逛逛</h2>
    </div>
    <div class="category-grid">
      <router-link
        v-for="category in categories"
        :key="category.id"
        :to="{ name: 'category', params: { id: category.id } }"
        class="category-tile"
      >
        <span class="category-icon">{{ category.name.slice(0, 1) }}</span>
        <span class="category-name">{{ category.name }}</span>
      </router-link>
    </div>

    <div class="section-head">
      <h2>大家都在看</h2>
      <span class="section-sub">按热度推荐</span>
    </div>
    <div v-if="loading" class="product-grid">
      <div v-for="index in 4" :key="index" class="product-skeleton" />
    </div>
    <div v-else-if="products.length" class="product-grid">
      <ProductCard
        v-for="product in products"
        :key="product.id"
        :product="product"
      />
    </div>
    <div v-else class="empty-panel">
      商品即将上架，敬请期待
    </div>
  </section>
</template>

<style scoped>
.discovery-panel {
  margin-top: 14px;
}

.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin: 0 2px 8px;
}

.section-head h2 {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
}

.section-sub {
  font-size: 10px;
  color: var(--color-text-secondary);
}

.category-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 18px;
}

.category-tile {
  background: var(--color-card);
  border-radius: 12px;
  box-shadow: var(--shadow-card);
  padding: 12px 4px 10px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  color: inherit;
  text-decoration: none;
}

.category-icon {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  font-weight: 800;
}

.category-name {
  font-size: 11px;
  font-weight: 600;
}

.product-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.product-skeleton {
  aspect-ratio: 0.72;
  border-radius: var(--radius-card);
  background: linear-gradient(90deg, #f0f1f3, #f7f8fa, #f0f1f3);
}

.empty-panel {
  background: var(--color-card);
  border-radius: var(--radius-card);
  padding: 28px 16px;
  text-align: center;
  font-size: 12px;
  color: var(--color-text-secondary);
}
</style>
```

- [ ] **Step 4: 改写 HomeView**

保留 M0 E2E 依赖的“你好，小鹿”文本：

```vue
<script setup lang="ts">
import { computed } from 'vue'
import { showToast } from 'vant'

import ProductDiscoveryPanel from '@/components/catalog/ProductDiscoveryPanel.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const displayName = computed(
  () => auth.user?.nickname || auth.user?.username || '',
)

const examples = ['找一件蓝色薄衬衫', '200 元以内的运动鞋', '通勤双肩包']

function handleExample(): void {
  showToast('AI 导购将在 M4 上线')
}
</script>

<template>
  <div class="page home-page">
    <header class="home-header">
      <div class="brand">
        <div class="brand-logo" aria-hidden="true">AI</div>
        <div>
          <h1 class="brand-title">AI 找货</h1>
          <div class="brand-sub">对话式导购助手</div>
        </div>
      </div>
    </header>
    <div class="home-body">
      <section class="greeting-card">
        <div class="greeting-avatar" aria-hidden="true">AI</div>
        <div class="greeting-text">
          <h2>你好，{{ displayName }}</h2>
          <p>说出你想找的，AI 帮你挑合适的款。</p>
        </div>
      </section>

      <div class="example-chips">
        <button
          v-for="example in examples"
          :key="example"
          type="button"
          class="example-chip"
          @click="handleExample"
        >
          {{ example }}
        </button>
      </div>

      <ProductDiscoveryPanel />
    </div>
  </div>
</template>

<style scoped>
.home-page {
  min-height: calc(100vh - 56px);
  min-height: calc(100vh - 56px - env(safe-area-inset-bottom));
  min-height: calc(100dvh - 56px - env(safe-area-inset-bottom));
  background: var(--color-bg);
}

.home-header {
  height: 58px;
  background: var(--color-card);
  display: flex;
  align-items: center;
  padding: 0 16px;
  border-bottom: 1px solid var(--color-border);
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand-logo {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: var(--color-primary-gradient);
  color: #fff;
  font-size: 12px;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
}

.brand-title {
  font-size: 15px;
  font-weight: 700;
  line-height: 1.1;
  margin: 0;
}

.brand-sub {
  font-size: 10px;
  color: var(--color-text-secondary);
  margin-top: 2px;
}

.home-body {
  padding: 14px;
}

.greeting-card {
  background: var(--color-card);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  padding: 16px;
  display: flex;
  gap: 12px;
  align-items: center;
}

.greeting-avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: var(--color-primary-gradient);
  color: #fff;
  font-size: 14px;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
}

.greeting-text h2 {
  margin: 0;
  font-size: 15px;
}

.greeting-text p {
  margin: 4px 0 0;
  font-size: 11px;
  color: var(--color-text-secondary);
}

.example-chips {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding: 10px 0 2px;
  scrollbar-width: none;
}

.example-chips::-webkit-scrollbar {
  display: none;
}

.example-chip {
  flex: 0 0 auto;
  border: 1px solid var(--color-primary-border);
  background: var(--color-primary-soft);
  color: var(--color-primary);
  border-radius: 999px;
  padding: 7px 11px;
  font-size: 11px;
  line-height: 1.2;
}

.example-chip:active {
  opacity: 0.8;
}
</style>
```

- [ ] **Step 5: 运行构建**

```bash
cd /d/develop/graduation-project-new/frontend
npm run build
```

Expected: PASS。若后端未启动，构建不受影响。

- [ ] **Step 6: 提交**

```bash
git add frontend/src/components/catalog frontend/src/views/user/HomeView.vue
git commit -m "feat: add reusable product discovery panel"
```

---

### Task 14: 分类商品列表页

**Files:**
- Create: `frontend/src/views/user/CategoryView.vue`
- Modify: `frontend/src/router/index.ts`

- [ ] **Step 1: 写 CategoryView**

```vue
<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from 'vant'

import { fetchProducts } from '@/api/catalog'
import ProductCard from '@/components/catalog/ProductCard.vue'
import { useCatalogStore } from '@/stores/catalog'
import type { ProductSort, ProductSummary } from '@/types/catalog'
import { getErrorMessage } from '@/utils/error'

const route = useRoute()
const router = useRouter()
const catalog = useCatalogStore()

const categoryId = computed(() => Number(route.params.id))
const category = computed(() => catalog.find(categoryId.value))
const parentCategory = computed(() => {
  const current = category.value
  if (!current?.parent_id) {
    return null
  }
  return catalog.find(current.parent_id)
})

const keyword = ref('')
const sort = ref<ProductSort>('recommended')
const items = ref<ProductSummary[]>([])
const page = ref(1)
const total = ref(0)
const listLoading = ref(false)
const finished = ref(false)
const loadError = ref('')

const sortOptions = [
  { text: '推荐', value: 'recommended' },
  { text: '价格升序', value: 'price_asc' },
  { text: '价格降序', value: 'price_desc' },
]

const headerTitle = computed(() => category.value?.name || '商品列表')
const headerSub = computed(() => parentCategory.value?.name || '')

function goBack(): void {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.replace('/')
  }
}

async function loadMore(): Promise<void> {
  if (finished.value || listLoading.value) {
    return
  }
  const nextPage = page.value
  listLoading.value = true
  loadError.value = ''
  try {
    const data = await fetchProducts({
      category_id: categoryId.value,
      q: keyword.value.trim() || undefined,
      page: nextPage,
      page_size: 20,
      sort: sort.value,
    })
    if (nextPage === 1) {
      items.value = data.items
    } else {
      items.value.push(...data.items)
    }
    total.value = data.total
    page.value = nextPage + 1
    finished.value = items.value.length >= data.total || data.items.length === 0
  } catch (error) {
    loadError.value = getErrorMessage(error)
    showToast(loadError.value)
    finished.value = true
  } finally {
    listLoading.value = false
  }
}

function reload(): void {
  page.value = 1
  items.value = []
  total.value = 0
  finished.value = false
  listLoading.value = true
  void loadMore()
}

function handleSearch(): void {
  reload()
}

function handleSortChange(): void {
  reload()
}

watch(
  () => route.params.id,
  () => {
    reload()
  },
)

onMounted(async () => {
  await catalog.load()
  reload()
})
</script>

<template>
  <div class="page category-page">
    <header class="page-header">
      <button type="button" class="icon-button" aria-label="返回" @click="goBack">
        <van-icon name="arrow-left" size="18" />
      </button>
      <div class="header-title">
        <h1>{{ headerTitle }}</h1>
        <span v-if="headerSub">{{ headerSub }}</span>
      </div>
      <span class="header-spacer" />
    </header>

    <div class="filter-bar">
      <van-search
        v-model="keyword"
        placeholder="搜索商品、品牌"
        shape="round"
        background="transparent"
        @search="handleSearch"
        @clear="handleSearch"
      />
      <van-dropdown-menu>
        <van-dropdown-item
          v-model="sort"
          :options="sortOptions"
          @change="handleSortChange"
        />
      </van-dropdown-menu>
    </div>

    <div class="list-summary">
      共 {{ total }} 件商品
    </div>

    <van-list
      v-model:loading="listLoading"
      :finished="finished"
      finished-text="没有更多了"
      @load="loadMore"
    >
      <div v-if="items.length" class="product-grid">
        <ProductCard
          v-for="product in items"
          :key="product.id"
          :product="product"
        />
      </div>
      <van-empty
        v-else-if="finished && !loadError"
        description="没有找到符合条件的商品"
      />
    </van-list>
  </div>
</template>

<style scoped>
.category-page {
  min-height: 100vh;
  min-height: 100dvh;
  background: var(--color-bg);
  padding-bottom: 20px;
}

.page-header {
  height: 58px;
  background: var(--color-card);
  display: flex;
  align-items: center;
  padding: 0 8px;
  border-bottom: 1px solid var(--color-border);
  position: sticky;
  top: 0;
  z-index: 10;
}

.icon-button {
  width: 44px;
  height: 44px;
  border: 0;
  background: transparent;
  color: var(--color-text);
  display: flex;
  align-items: center;
  justify-content: center;
}

.header-title {
  flex: 1;
  min-width: 0;
  text-align: center;
}

.header-title h1 {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
}

.header-title span {
  display: block;
  font-size: 9px;
  color: var(--color-text-secondary);
  margin-top: 1px;
}

.header-spacer {
  width: 44px;
  flex: 0 0 auto;
}

.filter-bar {
  background: var(--color-card);
  padding: 2px 6px 4px;
  display: flex;
  align-items: center;
  gap: 4px;
}

.filter-bar :deep(.van-search) {
  flex: 1;
  padding: 6px 4px;
}

.filter-bar :deep(.van-dropdown-menu) {
  width: 92px;
  flex: 0 0 auto;
}

.filter-bar :deep(.van-dropdown-menu__bar) {
  box-shadow: none;
  background: transparent;
}

.list-summary {
  padding: 10px 14px 2px;
  font-size: 10px;
  color: var(--color-text-secondary);
}

.product-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  padding: 8px 14px 16px;
}
</style>
```

- [ ] **Step 2: 注册路由**

`frontend/src/router/index.ts` 在 `/` 路由之前增加：

```ts
{
  path: '/category/:id',
  name: 'category',
  component: () => import('@/views/user/CategoryView.vue'),
  meta: { requiresAuth: true },
},
```

并给 router 增加：

```ts
scrollBehavior: () => ({ top: 0 }),
```

- [ ] **Step 3: 运行构建**

```bash
npm run build
```

Expected: PASS。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/views/user/CategoryView.vue frontend/src/router/index.ts
git commit -m "feat: add category product list page"
```

---

### Task 15: 商品详情页

**Files:**
- Create: `frontend/src/views/user/ProductDetailView.vue`
- Modify: `frontend/src/router/index.ts`

- [ ] **Step 1: 写 ProductDetailView**

```vue
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from 'vant'

import { fetchProduct } from '@/api/catalog'
import ProductImage from '@/components/catalog/ProductImage.vue'
import { useFavoritesStore } from '@/stores/favorites'
import type { ProductDetail, ProductSku } from '@/types/catalog'
import { colorHex } from '@/utils/colors'
import { getErrorMessage } from '@/utils/error'
import { formatAttributeValue, formatPrice, formatRange } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const favorites = useFavoritesStore()

const product = ref<ProductDetail | null>(null)
const loading = ref(true)
const errorMessage = ref('')
const selectedColor = ref('')
const selectedSize = ref('')
const favorited = ref(false)
const showSizeChart = ref(false)

const colors = computed(() => {
  const seen = new Set<string>()
  const result: string[] = []
  for (const sku of product.value?.skus ?? []) {
    if (!seen.has(sku.color)) {
      seen.add(sku.color)
      result.push(sku.color)
    }
  }
  return result
})

const sizesForColor = computed<ProductSku[]>(() =>
  (product.value?.skus ?? []).filter((sku) => sku.color === selectedColor.value),
)

const selectedSku = computed<ProductSku | null>(
  () => sizesForColor.value.find((sku) => sku.size === selectedSize.value) ?? null,
)

const displayPrice = computed(() => selectedSku.value?.price ?? product.value?.price ?? 0)
const showSizeSelector = computed(() => {
  if (sizesForColor.value.length > 1) {
    return true
  }
  return sizesForColor.value.length === 1 && sizesForColor.value[0].size !== '均码'
})

const subtitle = computed(() => {
  const attributes = product.value?.attributes
  if (!attributes) {
    return ''
  }
  return ['material', 'fit', 'thickness', 'style', 'gender']
    .map((key) => attributes[key])
    .filter((value): value is string => typeof value === 'string' && value.length > 0)
    .join(' · ')
})

const attributeItems = computed(() => {
  const current = product.value
  if (!current) {
    return []
  }
  return current.attribute_schema.attributes
    .filter((attribute) => !['key_features', 'size'].includes(attribute.key))
    .map((attribute) => ({
      label: attribute.label,
      value: formatAttributeValue(current.attributes[attribute.key]),
    }))
    .filter((item) => item.value.length > 0)
})

const keyFeatures = computed(() => {
  const value = product.value?.attributes.key_features
  return Array.isArray(value) ? value.map(String) : []
})

const sizeChartColumns = computed(() => {
  if (product.value?.size_chart?.type === 'shoes') {
    return ['尺码', '脚长(mm)']
  }
  return ['尺码', '身高(cm)', '体重(kg)', '胸围(cm)', '腰围(cm)']
})

function chartRowValues(row: Record<string, unknown>): string[] {
  if (product.value?.size_chart?.type === 'shoes') {
    return [String(row.size), formatRange(row.foot_length as number[] | undefined)]
  }
  return [
    String(row.size),
    formatRange(row.height as number[] | undefined),
    formatRange(row.weight as number[] | undefined),
    formatRange(row.chest as number[] | undefined),
    formatRange(row.waist as number[] | undefined),
  ]
}

function goBack(): void {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.replace('/')
  }
}

function selectSize(size: string): void {
  selectedSize.value = size
}

async function toggleFavorite(): Promise<void> {
  if (!product.value) {
    return
  }
  try {
    favorited.value = await favorites.toggle(product.value)
    showToast(favorited.value ? '已收藏' : '已取消收藏')
  } catch (error) {
    showToast(getErrorMessage(error))
  }
}

function placeholder(message: string): void {
  showToast(message)
}

async function loadProduct(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const detail = await fetchProduct(Number(route.params.id))
    product.value = detail
    selectedColor.value = detail.skus[0]?.color ?? ''
    const sizes = detail.skus.filter((sku) => sku.color === selectedColor.value)
    selectedSize.value =
      sizes.find((sku) => sku.stock > 0)?.size ?? sizes[0]?.size ?? ''
    favorited.value = detail.is_favorited
    await favorites.load()
    if (favorites.loaded) {
      favorited.value = favorites.isFavorite(detail.id)
    }
  } catch (error) {
    errorMessage.value = getErrorMessage(error)
  } finally {
    loading.value = false
  }
}

onMounted(loadProduct)
</script>

<template>
  <div class="page detail-page">
    <header class="page-header">
      <button type="button" class="icon-button" aria-label="返回" @click="goBack">
        <van-icon name="arrow-left" size="18" />
      </button>
      <span class="header-title">商品详情</span>
      <button
        type="button"
        class="icon-button"
        aria-label="购物车"
        @click="placeholder('购物车将在 M2 上线')"
      >
        <van-icon name="cart-o" size="18" />
      </button>
    </header>

    <div v-if="loading" class="state-panel">
      <van-loading size="22">加载中...</van-loading>
    </div>
    <van-empty v-else-if="errorMessage" :description="errorMessage" />
    <template v-else-if="product">
      <main class="detail-scroll">
        <van-swipe class="detail-swipe" :autoplay="0" indicator-color="#FF5A1F">
          <van-swipe-item v-for="image in product.images" :key="image">
            <ProductImage :src="image" :alt="product.title" />
          </van-swipe-item>
        </van-swipe>

        <section class="detail-body">
          <div class="price-row">
            <span class="price">
              <small>¥</small>{{ formatPrice(displayPrice) }}
            </span>
            <span class="sales">已售 {{ product.sales_count }}</span>
          </div>
          <h1 class="detail-title">{{ product.title }}</h1>
          <p v-if="subtitle" class="detail-sub">{{ subtitle }}</p>

          <div class="color-row">
            <span class="row-label">颜色</span>
            <button
              v-for="color in colors"
              :key="color"
              type="button"
              class="color-swatch"
              :class="{ active: selectedColor === color }"
              :style="{ background: colorHex(color) }"
              :aria-label="color"
              @click="selectedColor = color"
            />
            <span class="color-name">{{ selectedColor }}</span>
          </div>

          <div v-if="showSizeSelector" class="size-row">
            <span class="row-label">尺码</span>
            <button
              v-for="sku in sizesForColor"
              :key="sku.id"
              type="button"
              class="size-chip"
              :class="{ active: selectedSize === sku.size, disabled: sku.stock <= 0 }"
              :disabled="sku.stock <= 0"
              @click="selectSize(sku.size)"
            >
              {{ sku.size }}
            </button>
            <button
              v-if="product.size_chart"
              type="button"
              class="size-chart-link"
              @click="showSizeChart = true"
            >
              尺码表
            </button>
          </div>
          <div v-else class="size-row">
            <span class="row-label">尺码</span>
            <span class="single-size">均码</span>
          </div>

          <div class="stock-line">
            <template v-if="selectedSku">
              <span v-if="selectedSku.stock > 0">库存 {{ selectedSku.stock }} 件</span>
              <span v-else class="out-of-stock">当前尺码缺货</span>
            </template>
          </div>

          <div class="attribute-table">
            <div v-for="item in attributeItems" :key="item.label" class="attribute-row">
              <span>{{ item.label }}</span>
              <span>{{ item.value }}</span>
            </div>
            <div v-if="keyFeatures.length" class="feature-row">
              <span>设计细节</span>
              <div class="feature-tags">
                <van-tag
                  v-for="feature in keyFeatures"
                  :key="feature"
                  plain
                  type="primary"
                >
                  {{ feature }}
                </van-tag>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer class="bottom-bar">
        <button type="button" class="bottom-icon" @click="toggleFavorite">
          <van-icon :name="favorited ? 'like' : 'like-o'" size="19" />
          <span>{{ favorited ? '已收藏' : '收藏' }}</span>
        </button>
        <button
          type="button"
          class="bottom-icon"
          @click="placeholder('客服将在 M6 上线')"
        >
          <van-icon name="service-o" size="19" />
          <span>客服</span>
        </button>
        <button
          type="button"
          class="bottom-button ghost"
          @click="placeholder('购物车将在 M2 上线')"
        >
          加入购物车
        </button>
        <button
          type="button"
          class="bottom-button primary"
          @click="placeholder('立即购买将在 M2 上线')"
        >
          立即购买
        </button>
      </footer>

      <van-popup
        v-model:show="showSizeChart"
        position="bottom"
        round
        class="size-chart-popup"
      >
        <div class="popup-head">
          <h2>尺码表</h2>
          <button type="button" class="popup-close" @click="showSizeChart = false">
            <van-icon name="cross" />
          </button>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th v-for="column in sizeChartColumns" :key="column">{{ column }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in product.size_chart?.rows ?? []" :key="row.size">
                <td v-for="(value, index) in chartRowValues(row)" :key="index">
                  {{ value }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </van-popup>
    </template>
  </div>
</template>

<style scoped>
.detail-page {
  min-height: 100vh;
  min-height: 100dvh;
  background: var(--color-bg);
}

.page-header {
  height: 58px;
  background: var(--color-card);
  display: flex;
  align-items: center;
  padding: 0 8px;
  border-bottom: 1px solid var(--color-border);
  position: sticky;
  top: 0;
  z-index: 10;
}

.icon-button {
  width: 44px;
  height: 44px;
  border: 0;
  background: transparent;
  color: var(--color-text);
  display: flex;
  align-items: center;
  justify-content: center;
}

.header-title {
  flex: 1;
  text-align: center;
  font-size: 15px;
  font-weight: 700;
}

.state-panel {
  padding: 80px 0;
  display: flex;
  justify-content: center;
}

.detail-scroll {
  padding-bottom: 78px;
  padding-bottom: calc(78px + env(safe-area-inset-bottom));
}

.detail-swipe {
  background: var(--color-card);
}

.detail-body {
  background: var(--color-card);
  margin-top: 8px;
  padding: 14px;
}

.price-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}

.price {
  color: var(--color-price);
  font-size: 23px;
  font-weight: 800;
}

.price small {
  font-size: 11px;
  margin-right: 2px;
}

.sales {
  font-size: 10px;
  color: var(--color-text-secondary);
}

.detail-title {
  margin: 8px 0 0;
  font-size: 16px;
  line-height: 1.35;
}

.detail-sub {
  margin: 5px 0 0;
  font-size: 11px;
  color: var(--color-text-secondary);
}

.color-row,
.size-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 14px;
  flex-wrap: wrap;
}

.row-label {
  width: 30px;
  flex: 0 0 auto;
  font-size: 11px;
  color: var(--color-text-secondary);
}

.color-swatch {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: 2px solid transparent;
  padding: 0;
}

.color-swatch.active {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px #fff inset;
}

.color-name {
  font-size: 10.5px;
  color: var(--color-text-secondary);
}

.size-chip {
  min-width: 44px;
  height: 32px;
  padding: 0 10px;
  border-radius: 8px;
  border: 1px solid var(--color-border);
  background: var(--color-field-bg);
  color: var(--color-text);
  font-size: 12px;
}

.size-chip.active {
  border-color: var(--color-primary);
  color: var(--color-primary);
  background: var(--color-primary-soft);
  font-weight: 700;
}

.size-chip.disabled {
  color: var(--color-text-tertiary);
  text-decoration: line-through;
}

.size-chart-link {
  border: 0;
  background: transparent;
  color: #3b6fd4;
  font-size: 10px;
  padding: 6px 2px;
}

.single-size {
  font-size: 12px;
  color: var(--color-text);
}

.stock-line {
  min-height: 18px;
  margin-top: 8px;
  font-size: 10px;
  color: var(--color-text-secondary);
}

.out-of-stock {
  color: var(--color-price);
}

.attribute-table {
  margin-top: 8px;
  border-top: 1px solid var(--color-border);
}

.attribute-row,
.feature-row {
  display: flex;
  gap: 12px;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid var(--color-border);
  font-size: 11px;
}

.attribute-row span:first-child,
.feature-row > span {
  color: var(--color-text-secondary);
  flex: 0 0 52px;
}

.attribute-row span:last-child {
  text-align: right;
  flex: 1;
}

.feature-row {
  align-items: flex-start;
}

.feature-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  justify-content: flex-end;
}

.bottom-bar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--color-card);
  border-top: 1px solid var(--color-border);
  padding: 6px 10px;
  padding-bottom: calc(6px + env(safe-area-inset-bottom));
  display: flex;
  align-items: center;
  gap: 6px;
  z-index: 20;
}

.bottom-icon {
  width: 44px;
  height: 44px;
  border: 0;
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 9px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1px;
}

.bottom-button {
  flex: 1;
  height: 40px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  border: 0;
}

.bottom-button.ghost {
  background: var(--color-primary-soft);
  color: var(--color-primary);
  border: 1px solid var(--color-primary-border);
}

.bottom-button.primary {
  background: var(--color-primary-gradient);
  color: #fff;
}

.size-chart-popup {
  padding: 16px 14px calc(16px + env(safe-area-inset-bottom));
}

.popup-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.popup-head h2 {
  margin: 0;
  font-size: 16px;
}

.popup-close {
  width: 36px;
  height: 36px;
  border: 0;
  background: transparent;
  color: var(--color-text-secondary);
}

.table-wrap {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11px;
  text-align: center;
}

th,
td {
  padding: 8px 6px;
  border-bottom: 1px solid var(--color-border);
  white-space: nowrap;
}

th {
  color: var(--color-text-secondary);
  font-weight: 600;
  background: var(--color-field-bg);
}
</style>
```

- [ ] **Step 2: 注册路由**

在 `frontend/src/router/index.ts` 增加：

```ts
{
  path: '/product/:id',
  name: 'product-detail',
  component: () => import('@/views/user/ProductDetailView.vue'),
  meta: { requiresAuth: true },
},
```

- [ ] **Step 3: 运行构建**

```bash
npm run build
```

Expected: PASS。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/views/user/ProductDetailView.vue frontend/src/router/index.ts
git commit -m "feat: add product detail page"
```

---

### Task 16: 收藏页与 Me 入口

**Files:**
- Create: `frontend/src/views/user/FavoritesView.vue`
- Modify: `frontend/src/views/user/MeView.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/main.ts`

- [ ] **Step 1: 写 FavoritesView**

```vue
<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'

import ProductCard from '@/components/catalog/ProductCard.vue'
import { useFavoritesStore } from '@/stores/favorites'

const router = useRouter()
const favorites = useFavoritesStore()

function goBack(): void {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.replace('/me')
  }
}

onMounted(() => {
  void favorites.load(true)
})
</script>

<template>
  <div class="page favorites-page">
    <header class="page-header">
      <button type="button" class="icon-button" aria-label="返回" @click="goBack">
        <van-icon name="arrow-left" size="18" />
      </button>
      <span class="header-title">我的收藏</span>
      <span class="header-spacer" />
    </header>

    <div v-if="favorites.loading && !favorites.items.length" class="state-panel">
      <van-loading size="22">加载中...</van-loading>
    </div>
    <div v-else-if="favorites.items.length" class="favorites-body">
      <div class="product-grid">
        <ProductCard
          v-for="product in favorites.items"
          :key="product.id"
          :product="product"
        />
      </div>
    </div>
    <van-empty v-else description="还没有收藏的商品" />
  </div>
</template>

<style scoped>
.favorites-page {
  min-height: 100vh;
  min-height: 100dvh;
  background: var(--color-bg);
}

.page-header {
  height: 58px;
  background: var(--color-card);
  display: flex;
  align-items: center;
  padding: 0 8px;
  border-bottom: 1px solid var(--color-border);
  position: sticky;
  top: 0;
  z-index: 10;
}

.icon-button {
  width: 44px;
  height: 44px;
  border: 0;
  background: transparent;
  color: var(--color-text);
  display: flex;
  align-items: center;
  justify-content: center;
}

.header-title {
  flex: 1;
  text-align: center;
  font-size: 15px;
  font-weight: 700;
}

.header-spacer {
  width: 44px;
}

.state-panel {
  padding: 80px 0;
  display: flex;
  justify-content: center;
}

.favorites-body {
  padding: 12px 14px 20px;
}

.product-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
</style>
```

- [ ] **Step 2: 修改 MeView**

在 `<script setup>` 增加：

```ts
import { onMounted } from 'vue'
import { useFavoritesStore } from '@/stores/favorites'

const favorites = useFavoritesStore()

onMounted(() => {
  void favorites.load()
})
```

在 `handleLogout` 中 `auth.logout()` 前增加：

```ts
favorites.clear()
```

在“更多功能”占位卡位置替换为：

```vue
<van-cell-group inset class="me-menu">
  <van-cell
    title="我的收藏"
    is-link
    :value="favorites.items.length ? String(favorites.items.length) : ''"
    @click="router.push('/favorites')"
  />
  <van-cell title="我的订单" value="M2 上线" />
  <van-cell title="地址管理" value="M2 上线" />
  <van-cell title="导购会话" value="M4 上线" />
</van-cell-group>
```

并在样式末尾增加：

```css
.me-menu {
  margin-top: 10px;
  overflow: hidden;
  border-radius: var(--radius-card);
}
```

- [ ] **Step 3: 注册收藏路由**

在 `frontend/src/router/index.ts` 增加：

```ts
{
  path: '/favorites',
  name: 'favorites',
  component: () => import('@/views/user/FavoritesView.vue'),
  meta: { requiresAuth: true },
},
```

- [ ] **Step 4: 401 时清空收藏 store**

`frontend/src/main.ts`：

```ts
import { useFavoritesStore } from './stores/favorites'
```

在 `const auth = useAuthStore(pinia)` 后增加：

```ts
const favorites = useFavoritesStore(pinia)
```

在 `AUTH_EXPIRED_EVENT` 监听器中增加：

```ts
favorites.clear()
```

- [ ] **Step 5: 运行构建**

```bash
cd /d/develop/graduation-project-new/frontend
npm run build
```

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add frontend/src/views/user/FavoritesView.vue frontend/src/views/user/MeView.vue frontend/src/router/index.ts frontend/src/main.ts
git commit -m "feat: add favorites page and me entry"
```

---

### Task 17: E2E、README 与全量验收

**Files:**
- Create: `frontend/tests/e2e/catalog.spec.ts`
- Modify: `README.md`

- [ ] **Step 1: 写 E2E**

`frontend/tests/e2e/catalog.spec.ts`：

```ts
import { expect, test } from '@playwright/test'

test.beforeAll(async ({ request }) => {
  const health = await request.get('/api/health')
  expect(health.ok()).toBeTruthy()

  const products = await request.get('/api/products?page_size=1')
  expect(products.ok()).toBeTruthy()
  const body = await products.json()
  if (body.total === 0) {
    throw new Error('商品种子为空：请先运行 cd backend && python -m scripts.seed_catalog')
  }
})

test('列表 → 详情 → 收藏 → 我的收藏 → 取消收藏', async ({ page, request }) => {
  await page.goto('/login')
  await page.getByPlaceholder('用户名').fill('demo')
  await page.getByPlaceholder('密码').fill('demo123')
  await page.getByRole('button', { name: '登录', exact: true }).click()

  await expect(page).toHaveURL('/')
  await expect(page.getByText('你好，小鹿')).toBeVisible()
  await expect(page.getByText('按品类逛逛')).toBeVisible()

  await page.getByRole('link', { name: /服装/ }).first().click()
  await expect(page).toHaveURL(/\/category\/\d+/)
  await expect(page.locator('.product-card').first()).toBeVisible()

  await page.locator('.product-card').first().click()
  await expect(page).toHaveURL(/\/product\/\d+/)
  const productId = Number(page.url().match(/\/product\/(\d+)/)?.[1])
  expect(productId).toBeGreaterThan(0)
  await expect(page.locator('.detail-title')).not.toBeEmpty()

  const token = await page.evaluate(() =>
    localStorage.getItem('ai-shop-access-token'),
  )
  expect(token).toBeTruthy()
  await request.delete(`/api/products/${productId}/favorite`, {
    headers: { Authorization: `Bearer ${token}` },
  })

  await page.getByRole('button', { name: '收藏', exact: true }).click()
  await expect(page.getByText('已收藏', { exact: true })).toBeVisible()

  await page.goto('/me')
  await page.getByText('我的收藏', { exact: true }).click()
  await expect(page).toHaveURL('/favorites')
  await expect(
    page.locator(`a[href="/product/${productId}"]`).first(),
  ).toBeVisible()

  await page.locator(`a[href="/product/${productId}"]`).first().click()
  await expect(page).toHaveURL(new RegExp(`/product/${productId}$`))
  await page.getByRole('button', { name: '已收藏', exact: true }).click()
  await expect(page.getByText('已取消收藏', { exact: true })).toBeVisible()

  await page.goto('/favorites')
  await expect(
    page.locator(`a[href="/product/${productId}"]`),
  ).toHaveCount(0)
})
```

- [ ] **Step 2: 更新 README**

在“启动后端”的 `python -m scripts.seed_demo_user` 后增加：

```bash
python -m scripts.seed_catalog
```

在测试章节增加说明：

```markdown
商品 E2E 依赖已导入的商品种子与 `backend/static/products` 中 300 张图片：

```bash
cd backend
source .venv/Scripts/activate
python -m scripts.seed_catalog
```

商品种子 JSON 在 `backend/seeds/catalog/`。只有 CSV 或品类 schema 变更、且确认要重建时才运行：

```bash
python -m scripts.build_catalog_seed --force
```

不重建时直接运行 `seed_catalog` 即可；重复执行不会重复插入，也不会丢收藏。
```

在“重置开发数据库”命令末尾增加：

```bash
python -m scripts.seed_catalog
```

在“主要目录”中补：

```text
backend/seeds/catalog/   # 品类与商品种子 JSON（商品 JSON 由 CSV 生成）
```

- [ ] **Step 3: 跑后端全量测试**

```bash
cd /d/develop/graduation-project-new/backend
source .venv/Scripts/activate
python -m pytest -v
```

Expected: 全部 PASS。

- [ ] **Step 4: 跑前端构建**

```bash
cd /d/develop/graduation-project-new/frontend
npm run build
```

Expected: PASS。

- [ ] **Step 5: 跑 E2E**

确保数据库已迁移、`seed_demo_user` 与 `seed_catalog` 已执行、后端 8100 正在运行，然后：

```bash
cd /d/develop/graduation-project-new/frontend
npm run test:e2e
```

Expected: `auth.spec.ts` 与 `catalog.spec.ts` 全部 PASS。

- [ ] **Step 6: 提交**

```bash
git add frontend/tests/e2e/catalog.spec.ts README.md
git commit -m "test: add catalog discovery e2e"
```

---

### Task 18: 进度、交接与最终提交

**Files:**
- Modify: `docs/progress.md`
- Modify: `docs/implementation-handoff.md`

- [ ] **Step 1: 更新 progress.md**

在“模块记录”最上面增加：

```markdown
## 2026-11-13 · M1 商品域 + 种子数据 + 商品详情

- 状态：已完成
- 本次目标：建商品域四表与种子，打通品类树、商品列表/详情、收藏和商品详情页。
- 完成内容：
  - 后端：categories/products/product_skus/favorites 四表与迁移；品类树（合并 attribute_schema）、商品列表（筛选/分页/排序）、商品详情（SKU/尺码表/属性/is_favorited）、收藏增删查；`/static` 商品图挂载；可选登录依赖。
  - 种子：4 个一级 + 34 个叶子品类；300 个商品；实际 1108 条 SKU；300 张已有商品图；build（CSV→JSON）与 seed（JSON→DB upsert）分离；重复导入不重复、不丢收藏。
  - 前端：AI 找货 Tab 可复用商品发现组件；`/category/:id` 列表；`/product/:id` 详情；`/favorites` 收藏页；Me 页收藏入口；加购/立即购买/客服 toast 占位。
  - 测试：后端 pytest（新增 schema/API/seed/build 测试）；前端 build；Playwright “列表→详情→收藏” E2E。
- 改动文件 / 目录：
  - `backend/app/modules/catalog/`、`backend/alembic/versions/20261113_0002_create_catalog.py`
  - `backend/seeds/catalog/`、`backend/scripts/build_catalog_seed.py`、`backend/scripts/seed_catalog.py`
  - `backend/tests/`、`backend/app/main.py`、`backend/app/models.py`、`backend/app/modules/auth/deps.py`
  - `frontend/src/components/catalog/`、`frontend/src/views/user/`、`frontend/src/api/`、`frontend/src/stores/`、`frontend/src/types/`、`frontend/src/utils/`
  - `frontend/src/router/index.ts`、`frontend/src/main.ts`、`frontend/vite.config.ts`
  - `README.md`、`docs/`
- DB 迁移：`20261113_0002_create_catalog`
- 新增环境变量：无
- 测试与验收：
  - 命令：`cd backend && source .venv/Scripts/activate && python -m pytest -v`；`cd frontend && npm run build`；`cd frontend && npm run test:e2e`
  - 结果：后端全部通过；前端构建成功；E2E 通过（含 M0 认证回归）。
- 种子实际数量：商品 300、SKU 1108（服装 375、鞋靴 375、箱包 209、配饰 149）、图片 300。
- 遗留问题：
  - [后续] 商品搜索为 `ILIKE` 子串匹配，未接分词/向量检索；M4 再接混合检索。
  - [后续] `products.embedding` 已建列但保持 NULL，M3/M4 再生成向量。
  - [后续] 商品详情“好评率”、购物车、立即购买、客服为占位；M2/M3/M6 接入。
  - [后续] 尺码推荐卡片按计划留到 M4；M1 只提供尺码表与尺码选择。
  - [后续] `backend/static/products` 仍未单独备份；商品图不进 git。
- 下一模块依赖：M2 可直接复用商品/SKU 表、收藏用户态、Axios 客户端和详情页底部占位按钮；购物车落 SKU 时使用 `product_skus.id` 与库存。
- commit：见 `git log`（M1 分支 `m1-product-catalog`）
```

- [ ] **Step 2: 更新 handoff**

把“当前状态”中的 M0 行改为 M1 完成，并更新“下一步”：

```markdown
- 主项目骨架与商品域已完成：M0 认证/骨架，M1 品类/商品/SKU/收藏/商品详情。
- 下一步 M2：购物车、地址、订单、模拟支付/发货；复用 `product_skus`、`favorites` 的用户态、`/product/:id` 底部占位按钮。
```

- [ ] **Step 3: 最终检查 git 状态**

```bash
cd /d/develop/graduation-project-new
git status --short
git log --oneline -8
```

Expected: 工作区干净；能看到 M1 的提交。

- [ ] **Step 4: 提交文档**

```bash
git add docs/progress.md docs/implementation-handoff.md
git commit -m "docs: record M1 progress and handoff"
```

---

## 5. 完成标准自检

- [ ] 四表迁移可在空库执行，也能在 M0 库上从 `20261113_0001` 升级。
- [ ] `product_code` 唯一；重复 `seed_catalog` 不改变商品 id，不产生重复商品/SKU。
- [ ] `categories.json` 有 4 个一级 + 34 个叶子；每个叶子 2~3 个可筛选属性；`key_features` 为 tags。
- [ ] `products.json` 有 300 个商品、1108 条 SKU；每商品一图一色；`original_price >= price`；300 张图片存在。
- [ ] `GET /api/categories` 返回合并后的 `attribute_schema`；父级公共属性在叶子可见。
- [ ] `GET /api/products` 分页结构为 `{items,total,page,page_size}`；`sort` 三种；父品类含子类；未知品类 404。
- [ ] `GET /api/products/{id}` 公开；带有效 token 返回 `is_favorited`；无效 token 不报 401。
- [ ] 收藏 POST/DELETE 幂等；未登录 401；商品不存在 404。
- [ ] `/static/products/*` 可访问；Vite 代理 `/static` 到 8100。
- [ ] AI 找货 Tab 有可复用 `ProductDiscoveryPanel`，没有新增独立 Home 路由；M0 “你好，小鹿”断言仍通过。
- [ ] `/category/:id` 支持搜索、排序、分页；`/product/:id` 支持颜色/尺码/SKU/尺码表/属性/收藏；`/favorites` 可查看并取消收藏。
- [ ] 加购/立即购买/客服为 toast 占位；尺码推荐未实现。
- [ ] 后端 pytest、前端 build、Playwright E2E 全部通过。
- [ ] 设计文档 §7.2.2、§8.1、§8.2、§10.2 与实现一致；progress/handoff 已更新。

---

## 6. 实施结果与计划偏差（2026-11-13）

实施时先读了 4 个 CSV 的真实 token，发现初稿的「领型/袖长/图案」等属性在部分叶子没有真实变化（会退化成一堆单一值）。因此按“每个叶子 2~3 个真正可筛选属性”改成下表；代码、种子与测试均以下表为准。

### 6.1 实际 34 叶子可筛选属性

| 叶子 | 属性 1 | 属性 2 | 属性 3 |
|---|---|---|---|
| 衬衫 | collar_type 翻领/立领 | shoulder 落肩/常规肩 | hem 弧形/平直 |
| T恤 | neckline 圆领/V领 | sleeve_length 短袖/长袖 | hem 开衩/平直 |
| 裤装 | waist_type 高腰/中腰 | length 九分/长裤 | pocket_type 斜插袋/后口袋/无口袋 |
| 连衣裙 | neckline V领/圆领 | length 中长款/短款 | waist 收腰/直筒 |
| 外套 | collar_type 翻领/立领 | closure 双排扣/单排扣 | length 中长款/短款 |
| 针织衫 | neckline 圆领/V领 | sleeve_length 长袖/短袖 | pattern 麻花/条纹/纯色 |
| 卫衣 | hood 连帽/无帽 | drawstring 有/无 | pocket 袋鼠口袋/无口袋 |
| 半身裙 | waist_type 高腰/中腰 | length 中长款/短款 | silhouette A字/直筒 |
| 西装 | lapel 平驳领/戗驳领 | closure 单排扣/双排扣 | back_vent 有/无 |
| 风衣 | collar_type 翻领/立领 | closure 双排扣/单排扣 | length 中长款/短款 |
| 运动鞋 | closure 系带/一脚蹬 | sole 厚底/平底 | upper 网面/皮革 |
| 休闲鞋 | toe_shape 圆头/尖头 | sole 软底/橡胶底 | lace 撞色/同色 |
| 皮鞋 | toe_shape 圆头/尖头 | closure 系带/一脚蹬 | sole 橡胶底/皮革底 |
| 靴子 | shaft_height 短筒/中筒 | heel 粗跟/平底 | closure 松紧侧片/系带 |
| 帆布鞋 | height 低帮/高帮 | sole 硫化底/橡胶底 | lace 撞色/同色 |
| 凉鞋 | toe_shape 露趾/包头 | closure 搭扣/一脚蹬 | sole 轻便/厚底 |
| 拖鞋 | toe_shape 包头/露趾 | sole 软底/硬底 | anti_slip 防滑/普通 |
| 高跟鞋 | toe_shape 尖头/圆头 | heel 细跟/粗跟 | opening 浅口/包脚 |
| 双肩包 | capacity 大容量/常规 | laptop_sleeve 有/无 | closure 拉链/翻盖 |
| 手提包 | shape 定型/软身 | strap 可拆卸/固定 | closure 拉链/磁扣 |
| 单肩包 | strap 可调节/固定 | capacity 轻量/大容量 | closure 磁扣/拉链 |
| 斜挎包 | bag_size 小号/中号 | front_pocket 有/无 | closure 拉链/磁扣 |
| 钱包 | wallet_style 对折/长款 | rfid 有/无 | capacity 轻薄/多卡位 |
| 行李箱 | luggage_size 20寸/24寸 | wheel 万向轮/普通轮 | lock TSA锁/普通锁 |
| 托特包 | capacity 大容量/常规 | closure 开口/拉链 | carry_style 肩带/手提 |
| 腰包 | closure 搭扣/拉链 | multi_pocket 多隔层/单层 | waterproof 防泼水/普通 |
| 帽子 | adjustable 可调节/固定 | brim 弯檐/平檐 | breathable 有/无 |
| 围巾 | length 长款/短款 | pattern 格纹/纯色 | fringe 有/无 |
| 腰带 | width 宽3.5cm/窄版 | buckle 针扣/自动扣 | adjustable 可调节/固定 |
| 袜子 | length 中筒/短筒 | thickness 加厚/常规 | pattern 纯色/条纹 |
| 手套 | fingers 分指/连指 | touchscreen 支持/不支持 | lining 加绒/常规 |
| 墨镜 | frame 全框/半框 | lens 偏光/普通 | protection UV400/普通 |
| 项链 | length 锁骨链/长链 | pendant 有/无 | chain 细链/粗链 |
| 手表 | dial 圆形/方形 | water_resistance 30米/普通 | movement 石英/机械 |

`斜挎包/行李箱` 的尺寸属性改名为 `bag_size/luggage_size`，`钱包` 的款式改为 `wallet_style`，避免覆盖父级 `size/style`。

### 6.2 实施顺序与计划不同

为了让 API 测试有真实种子，实际顺序是：Task 1 → 2 → 3 → 9 → 10 → 11 → 4~8 → 12~18。计划中 Task 4 的“先跑种子再回来”说明可忽略。

### 6.3 测试与代码修正（已落地）

- `test_product_detail_is_public...` 取“服装品类第一个商品”，确保有 `size_chart=clothing`。
- 商品列表测试的 `page_size` 用 50（后端上限），不再用 100。
- 种子图片校验路径为 `BACKEND_DIR / "static" / main_image.removeprefix("/static/")`。
- `CategoryView` 用 `requestSeq` 防止筛选/路由切换时旧请求覆盖新结果；`van-list` 设 `:immediate-check="false"`，由 `reload()` 主动加载首屏。
- 详情页收藏按钮加 `aria-label`（`收藏` / `取消收藏`），因为 Vant 图标字体会进入可访问名；E2E 用 aria-label 定位，不依赖可见文字。
- 详情页收藏列表加载单独 try/catch，失败时回退到详情接口的 `is_favorited`。
- `playwright.config.ts` 固定 `workers: 1`，避免 demo 账号在多个测试文件间并行登录/退出。
- E2E toast 用 `.van-toast__text` 定位，避免与底部按钮“已收藏”文字冲突。

### 6.4 实际验收结果

- 后端：`70 passed`（45.52s）。
- 前端：`npm run build` 通过，`vue-tsc` 无报错。
- E2E：`3 passed`（13.2s），含 M0 认证回归。
- 种子：300 商品、1108 SKU、300 图片；重复执行 `seed_catalog` 后数量不变，收藏保留。
