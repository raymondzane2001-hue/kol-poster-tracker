#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KOL Poster Tracker
------------------
读取一批活动/会议海报图片，识别每张海报上出现的 KOL，
并汇总每位 KOL 在所有海报中被覆盖的次数。

用法:
    python kol_tracker.py --posters ./posters --kols ./kols.csv --out ./output

依赖一个支持视觉(图片)输入的大模型 API。默认使用 OpenAI，
你也可以在 .env 里改成别的兼容服务。
"""

import argparse
import base64
import csv
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    print("缺少依赖，请先运行: pip install -r requirements.txt")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv 是可选的，没有也能从系统环境变量读取

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
MODEL = os.getenv("VISION_MODEL", "gpt-4o")


def load_kols(path: Path):
    """从 CSV 读取 KOL 名单。第一列是 KOL 名字，其余列是别名/ID(可选)。"""
    kols = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            row = [c.strip() for c in row if c.strip()]
            if not row:
                continue
            # 跳过表头
            if row[0].lower() in ("name", "kol", "名字", "姓名"):
                continue
            name = row[0]
            aliases = row[1:]
            kols[name] = aliases
    return kols


def encode_image(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def build_prompt(kol_names):
    roster = "\n".join(f"- {n}" for n in kol_names)
    return f"""你是一个帮助市场营销团队统计 KOL 曝光的助手。

这是我们关注的 KOL 名单：
{roster}

请仔细看这张海报图片，找出图中出现的、属于上面名单里的 KOL
（可能以姓名、头像配文字、社媒 ID 等形式出现）。

只用 JSON 回答，格式如下，不要任何多余文字：
{{
  "matched": ["名单中出现的KOL名字", "..."],
  "others": ["海报上出现但不在名单里的其他人名", "..."]
}}

如果没有任何名单中的 KOL 出现，matched 返回空数组 []。"""


def analyze_poster(client, image_path: Path, kol_names):
    b64 = encode_image(image_path)
    ext = image_path.suffix.lstrip(".").lower()
    if ext == "jpg":
        ext = "jpeg"

    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": build_prompt(kol_names)},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/{ext};base64,{b64}"},
                    },
                ],
            }
        ],
        max_tokens=600,
    )
    text = resp.choices[0].message.content.strip()
    # 去掉可能的 ```json 代码块包裹
    text = text.replace("```json", "").replace("```", "").strip()
    try:
        data = json.loads(text)
        return data.get("matched", []), data.get("others", [])
    except json.JSONDecodeError:
        print(f"  [警告] {image_path.name} 返回内容无法解析，已跳过。原始返回：{text[:120]}")
        return [], []


def main():
    parser = argparse.ArgumentParser(description="KOL 海报覆盖次数统计工具")
    parser.add_argument("--posters", default="./posters", help="海报图片所在文件夹")
    parser.add_argument("--kols", default="./kols.csv", help="KOL 名单 CSV 文件")
    parser.add_argument("--out", default="./output", help="结果输出文件夹")
    args = parser.parse_args()

    posters_dir = Path(args.posters)
    kols_path = Path(args.kols)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not os.getenv("OPENAI_API_KEY"):
        print("未检测到 OPENAI_API_KEY。请复制 .env.example 为 .env 并填入你的 API Key。")
        sys.exit(1)

    if not kols_path.exists():
        print(f"找不到 KOL 名单文件: {kols_path}")
        sys.exit(1)

    kols = load_kols(kols_path)
    if not kols:
        print("KOL 名单为空，请先在 CSV 里填入 KOL 名字。")
        sys.exit(1)

    images = sorted(
        p for p in posters_dir.iterdir() if p.suffix.lower() in IMAGE_EXTS
    )
    if not images:
        print(f"在 {posters_dir} 里没有找到海报图片。")
        sys.exit(1)

    client = OpenAI()
    counts = defaultdict(int)
    detail_rows = []
    unknown_names = defaultdict(int)

    print(f"共找到 {len(images)} 张海报，开始识别...\n")
    for i, img in enumerate(images, 1):
        print(f"[{i}/{len(images)}] 处理 {img.name} ...")
        matched, others = analyze_poster(client, img, list(kols.keys()))
        for name in matched:
            counts[name] += 1
        for name in others:
            unknown_names[name] += 1
        detail_rows.append({
            "poster": img.name,
            "matched_kols": ", ".join(matched) if matched else "(无)",
        })
        if matched:
            print(f"      命中: {', '.join(matched)}")

    # 确保名单里每个 KOL 都出现在汇总里(哪怕是 0 次)
    for name in kols:
        counts.setdefault(name, 0)

    # 写出汇总表
    summary_path = out_dir / "kol_summary.csv"
    with open(summary_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["KOL", "覆盖次数"])
        for name, c in sorted(counts.items(), key=lambda x: -x[1]):
            writer.writerow([name, c])

    # 写出明细表(每张海报命中了谁)
    detail_path = out_dir / "poster_detail.csv"
    with open(detail_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["poster", "matched_kols"])
        writer.writeheader()
        writer.writerows(detail_rows)

    # 名单外的人名(供你考虑要不要加进名单)
    if unknown_names:
        unknown_path = out_dir / "unlisted_names.csv"
        with open(unknown_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["名单外人名", "出现次数"])
            for name, c in sorted(unknown_names.items(), key=lambda x: -x[1]):
                writer.writerow([name, c])

    print("\n===== KOL 覆盖汇总 =====")
    for name, c in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {name}: {c} 次")
    print(f"\n结果已保存到: {out_dir.resolve()}")
    print(f"  - 汇总表: {summary_path.name}")
    print(f"  - 明细表: {detail_path.name}")
    if unknown_names:
        print(f"  - 名单外人名: unlisted_names.csv")


if __name__ == "__main__":
    main()
