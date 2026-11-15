#!/usr/bin/env python3
"""Generate and verify a small M3U of recent movies and mainland variety shows."""

import argparse
import concurrent.futures
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
SOURCES = (
    ("极速", "https://jszyapi.com/api.php/provide/vod/", 9, 30),
    ("火狐", "https://hhzyapi.com/api.php/provide/vod/", 9, 30),
    ("爱坤", "https://ikunzyapi.com/api.php/provide/vod/", 6, 31),
    ("魔都", "https://www.mdzyapi.com/api.php/provide/vod/", 10, 34),
)
ADULT = re.compile(r"情色|色情|性爱|成人|伦理|三級|三级|无码|無碼|成人视频", re.I)
SECRET = re.compile(r"token|secret|pass(?:word|wd)?|session|signature|credential|auth|sign|cookie|expires?", re.I)


def fetch(source, category, kind):
    label, base, _, _ = source
    query = urlencode({"ac": "detail", "t": category, "pg": 1})
    request = Request(base + "?" + query, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(request, timeout=18) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError("接口响应过大")
        data = json.loads(raw)
        if not isinstance(data.get("list"), list):
            raise ValueError("接口未返回节目列表")
        print(f"{label} {kind}: {len(data['list'])} 条", flush=True)
        return kind, data["list"]
    except (OSError, ValueError, TypeError) as error:
        print(f"{label} {kind} 获取失败: {error}", file=sys.stderr, flush=True)
        return kind, []


def safe_url(value):
    try:
        if any(char in value for char in '\r\n"'):
            return False
        url = urlsplit(value)
        if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password or "|" in value:
            return False
        if not re.search(r"\.(?:m3u8|mp4)(?:$|/)", url.path, re.I):
            return False
        return not any(SECRET.search(key) for key, _ in parse_qsl(url.query, keep_blank_values=True))
    except ValueError:
        return False


def clean(value):
    return re.sub(r'["\r\n,]', " ", str(value or "")).strip()


def select(entries, limit):
    """Choose recent titles and at most two distinct-host lines per title."""
    choices = defaultdict(list)
    episodes = {}
    hosts = defaultdict(set)
    for item in sorted(entries, key=lambda x: x.get("vod_time", ""), reverse=True):
        title = clean(item.get("vod_name"))
        classification = str(item.get("vod_class") or "") + " " + str(item.get("type_name") or "")
        if not title or ADULT.search(title + " " + classification):
            continue
        key = re.sub(r"[\s\W_]+", "", title).casefold()
        if not key:
            continue
        for group in str(item.get("vod_play_url") or "").split("$$$"):
            raw_episodes = [part for part in group.split("#") if "$" in part]
            if not raw_episodes:
                continue
            episode, url = raw_episodes[-1].split("$", 1)
            episode, url = clean(episode), url.strip()
            if not safe_url(url) or ADULT.search(episode):
                continue
            host = urlsplit(url).hostname.lower()
            if host in hosts[key] or len(hosts[key]) >= 2:
                continue
            if key in episodes and episodes[key] != episode:
                continue
            episodes[key] = episode
            hosts[key].add(host)
            logo = str(item.get("vod_pic") or "").strip()
            if not urlsplit(logo).scheme in ("http", "https") or any(c in logo for c in '",\r\n'):
                logo = ""
            choices[key].append((title, episode, logo, url))
    # First cover as many titles as possible, then add a second host if space allows.
    result = []
    for index in (0, 1):
        for options in choices.values():
            if len(options) > index:
                result.append(options[index])
                if len(result) == limit:
                    return result
    return result


def main():
    parser = argparse.ArgumentParser(description="汇集并验证最新电影和大陆综艺，生成 M3U")
    parser.add_argument("--output", type=Path, default=ROOT / "vod-playable.m3u")
    parser.add_argument("--ffmpeg", default=shutil.which("ffmpeg"), help="ffmpeg 可执行文件路径")
    parser.add_argument("--limit", type=int, default=60, help="候选线路数（默认 60，最多 60）")
    args = parser.parse_args()
    if not args.ffmpeg or not Path(args.ffmpeg).is_file():
        parser.error("需要 ffmpeg，请通过 --ffmpeg 指定可执行文件")
    if not 2 <= args.limit <= 60:
        parser.error("--limit 必须在 2 到 60 之间")
    if args.output.resolve() == (ROOT / "playable.m3u").resolve():
        parser.error("不能覆盖直播文件 playable.m3u")
    items = {"电影": [], "综艺": []}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(fetch, source, category, kind)
                   for source in SOURCES
                   for category, kind in ((source[2], "电影"), (source[3], "综艺"))]
        for future in concurrent.futures.as_completed(futures):
            kind, result = future.result()
            items[kind].extend(result)
    lines = ["#EXTM3U"]
    for kind, limit in (("电影", args.limit // 2), ("综艺", args.limit - args.limit // 2)):
        selected = select(items[kind], limit)
        print(f"{kind}: {len(selected)} 条候选线路", flush=True)
        for title, episode, logo, url in selected:
            name = f"{title} · {episode}" if kind == "综艺" and episode else title
            tv_type = "movie" if kind == "电影" else "series"
            lines.append(f'#EXTINF:-1 tvg-name="{name}" tvg-logo="{logo}" group-title="{kind}" type="{tv_type}",{name}')
            lines.append(url)
    if len(lines) == 1:
        parser.exit(1, "没有获取到合格的候选地址，原输出未变。\n")
    # Separate files keep every intermediate result away from the live-TV list.
    candidate = ROOT / "vod-candidates.m3u"
    report = ROOT / "vod-probe-report.json"
    probed = ROOT / "vod-probed.m3u"
    candidate.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="vod-check-") as tmp:
        validated = Path(tmp) / "validated.m3u"
        try:
            subprocess.run([sys.executable, str(ROOT / "probe_iptv.py"), "--input", str(candidate),
                            "--output", str(probed), "--report", str(report)], check=True)
            subprocess.run([sys.executable, str(ROOT / "verify_playback.py"), "--ffmpeg", args.ffmpeg,
                            "--report", str(report), "--output", str(validated)], check=True)
            content = validated.read_text(encoding="utf-8")
            if "#EXTINF:" not in content:
                parser.exit(1, "候选均未通过播放测试，原输出未变。\n")
            args.output.write_text(content, encoding="utf-8")
        except (OSError, subprocess.CalledProcessError) as error:
            parser.exit(1, f"播放验证失败，原输出未变: {error}\n")
    print(f"已生成 {args.output}；仅代表短时读取与单帧解码成功，不代表长期可用。", flush=True)


if __name__ == "__main__":
    main()
