#!/usr/bin/env python3
"""Publish a tested VOD playlist only when coverage remains usable."""

import argparse
import re
from pathlib import Path
from prepare_public import safe_entries


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--previous", type=Path)
    args = parser.parse_args()
    entries = [entry for entry in safe_entries(args.candidate)
               if re.search(r'tvg-logo="https?://[^\"]+"', entry[0])]
    previous = safe_entries(args.previous) if args.previous and args.previous.exists() else []
    categories = {group for group in ("电影", "综艺") if any(f'group-title="{group}"' in info for info, _, _ in entries)}
    if len(entries) < 6 or len(categories) < 2:
        parser.error("电影或综艺数量不足，保留旧版")
    if previous and len(entries) < len(previous) * 0.5:
        parser.error("候选数不足上一版一半，保留旧版")
    lines = ["#EXTM3U"]
    for info, directives, url in entries:
        lines.extend([info, *directives, url])
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"候选通过安全和数量检查：{len(entries)} 条，涵盖电影和综艺。")


if __name__ == "__main__":
    main()
