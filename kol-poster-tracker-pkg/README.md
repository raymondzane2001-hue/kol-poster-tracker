# KOL Poster Tracker · 海报 KOL 覆盖统计工具

一个给市场营销团队用的小工具：把一批活动 / 会议海报丢进去，自动识别每张海报上出现的 KOL，并汇总每位 KOL 一共被覆盖了多少次。

不用再人工一张张数海报了。

## 它能做什么

- 批量读取一个文件夹里的海报图片（jpg / png / webp 等）
- 用视觉大模型识别海报上出现的 KOL（名字、头像配文、社媒 ID 等）
- 对照你提供的 KOL 名单，统计每人被覆盖的次数
- 顺便列出"名单外"出现的人名，方便你决定要不要补进名单
- 结果导出成 CSV，可以直接用 Excel 打开

## 输出结果

运行后会在 `output/` 文件夹生成：

| 文件 | 内容 |
| --- | --- |
| `kol_summary.csv` | 每个 KOL 的总覆盖次数（核心结果） |
| `poster_detail.csv` | 每张海报分别命中了哪些 KOL |
| `unlisted_names.csv` | 海报上出现、但不在你名单里的人名 |

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key

复制 `.env.example` 为 `.env`，填入你的 OpenAI API Key：

```
OPENAI_API_KEY=sk-你的key
```

### 3. 准备 KOL 名单

编辑 `kols.csv`，一行一个 KOL。第一列是名字，后面可以补别名或社媒 ID（可选）：

```csv
张伟,@weizhang,Wei Zhang
李娜,@lina_official
王芳
```

### 4. 放入海报

把所有海报图片放进 `posters/` 文件夹。

### 5. 运行

```bash
python kol_tracker.py
```

或者自定义路径：

```bash
python kol_tracker.py --posters ./我的海报 --kols ./名单.csv --out ./结果
```

## 说明

- 识别由视觉大模型完成，结果准确率取决于海报清晰度和模型能力；建议跑完后用 `poster_detail.csv` 抽查几张核对一下。
- 默认模型是 `gpt-4o`，可以在 `.env` 里通过 `VISION_MODEL` 改成别的支持图片输入的模型。
- 每张海报会调用一次 API，海报很多时会产生相应的 API 费用，请留意。

## License

MIT
