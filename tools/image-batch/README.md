# 商品图批量生成器

本地 Gradio 网页工具：读取商品 CSV，按固定模板逐条调用火山方舟 Seedream，批量生成商品图并按 `{id}_{color}.png` 落盘。

> 参考 `D:\develop\vibecoding\demo.py` 的 Seedream 调用方式改写；**原项目文件不做任何修改**。

---

## 快速开始

双击 `run.bat`，或：

```bash
"D:\develop\vibecoding\.venv\Scripts\python.exe" app.py
```

浏览器会自动打开 `http://127.0.0.1:7860`。

现有虚拟环境已经装了 Gradio 6.31、requests、Pillow、python-dotenv，无需重新安装；换机器时按 `requirements.txt` 安装。

---

## API Key 配置

工具按以下顺序找 Key：

1. 本目录 `.env`
2. `D:\develop\vibecoding\.env`

如果 `vibecoding` 的 `.env` 已经配好，**直接运行即可**。也可以在工具目录复制 `.env.example` 为 `.env`：

```text
ARK_API_KEY=ark-xxxx
ARK_IMAGE_MODEL=doubao-seedream-5-0-flash-260915
```

兼容 `HUOSHAN_API_KEY`。

---

## CSV 格式

必须包含以下 11 列（英文表头）：

```text
id,category,subcategory,color,color_hex,material,fit,thickness,style,gender,key_feature
```

正式清单已按品类拆成四个文件，每个 75 条：

```text
data/服装.csv   C001~C075
data/鞋靴.csv   S001~S075
data/箱包.csv   B001~B075
data/配饰.csv   A001~A075
```

改品类/颜色/材质后重新生成：`python make_catalog.py`。示例见 `data/sample_products.csv`，也可以在界面点「下载 CSV 模板」。

| 列 | 说明 | 示例 |
|---|---|---|
| id | 商品 ID，决定文件名 | C001 |
| category | 一级品类 | 服装 |
| subcategory | 叶子品类 | 衬衫 |
| color | 颜色中文名 | 蓝色 |
| color_hex | 颜色参考值 | #2F5FAF |
| material | 材质 | 纯棉 |
| fit | 版型 | 常规 |
| thickness | 厚薄 | 薄款 |
| style | 风格 | 休闲 |
| gender | 适用性别 | 男 |
| key_feature | 关键特征 | 翻领、单排扣、左胸口袋 |

CSV 用 UTF-8（Excel 导出带 BOM 也支持），GBK 会自动兜底。

---

## 提示词模板

默认模板在 `prompts.py` 的 `DEFAULT_TEMPLATE`，界面里可直接编辑。支持占位符：

```text
{id} {category} {subcategory} {color} {color_hex} {material}
{fit} {thickness} {style} {gender} {key_feature}
{composition} {background}
```

- `{composition}` 按品类自动填：服装平铺、裤装平铺、连衣裙隐形模特、鞋靴 45°、箱包 3/4、配饰俯拍。
- `{background}` 对白色/米白商品自动改用浅灰 `#F2F2F2`，避免轮廓和背景融合。

改了模板可以先点「预览首条提示词」，确认无误再批量。

---

## 批量参数

| 参数 | 默认 | 说明 |
|---|---|---|
| 分辨率 | 1K | 1024 足够首页/详情页；关键商品可单独用 2K 重生成 |
| 并发数 | 2 | 建议 2，最高 3；太高容易触发限流 |
| 失败重试 | 2 | 超时、429、5xx 会指数退避重试；401/400 不重试 |
| 强制重生成 | 关 | 覆盖已有文件 |
| 跳过已存在文件 | 开 | 断点续跑的关键；已有文件直接跳过 |
| 输出目录 | `backend/static/products` | 可直接被后端静态目录使用 |

---

## 断点续跑与失败重试

- 每完成一条，状态写入 `data/batch_status.json`。
- 失败项写入 `data/failed.csv`。
- 中断后重新打开工具，再次上传同一个 CSV，保持「跳过已存在文件」开启，即可从断点继续。
- 点「重试失败项」会读取 `failed.csv` 并强制重生成失败项。
- 全部成功后，`failed.csv` 会被清空（只保留表头）。

---

## 停止行为

「停止」是**软停止**：当前已经发出的 API 请求会跑完，之后不再发起新请求。Seedream 单张可能等 30~180 秒，所以点击后请等当前请求结束。要硬中断直接关闭终端/页面。

---

## 输出与下载

- 命名：`{id}_{color}.png`，例：`C001_蓝色.png`。
- 颜色里的空格、斜杠等会被替换为下划线。
- 「打包下载 ZIP」会把输出目录下所有 PNG 打成 `data/product_images_*.zip`。

---

## 常见问题

| 问题 | 处理 |
|---|---|
| 启动后显示 API Key 未配置 | 检查本目录 `.env` 或 `vibecoding/.env` 里的 `ARK_API_KEY` |
| HTTP 401 / 403 | Key 无效或无权限，检查火山方舟控制台 |
| HTTP 429 | 并发调低到 1~2，等待后重试 |
| 单张超时 | Seedream 出图慢，重试即可；可把并发降到 1 |
| CSV 校验失败 | 检查表头是否为 11 个英文列、id 是否重复 |
| 白色商品看不清 | 模板里的 `{background}` 已自动处理；仍不行就手动改成 `#F2F2F2` |
| 生成图有文字/logo | 模板已写禁止；仍出现就重生成该条，或加强否定描述 |
| 终端里中文文件名乱码 | Windows 控制台编码问题，文件名本身正确，在资源管理器里查看即可 |
| 生成成功但页面报 `Cannot move ... allowed_paths` | 图片在输出目录但 Gradio 不允许读取；默认输出目录已加入 `launch(allowed_paths=...)`，自定义目录需同样加入 |

---

## 文件结构

```text
tools/image-batch/
├── app.py                 # Gradio 界面 + 批量编排
├── seedream.py            # Seedream API 客户端（参考 demo.py 改写）
├── prompts.py             # 提示词模板 + 品类构图映射
├── make_catalog.py        # 生成四个品类的正式清单
├── batch.py               # CSV 读取、队列、重试、状态、ZIP
├── requirements.txt
├── .env.example
├── run.bat
├── README.md
└── data/
    ├── sample_products.csv
    ├── batch_status.json  # 运行时生成
    └── failed.csv         # 运行时生成
```
