#!/usr/bin/env python3
"""Collect configured M3U playlists into a compact CCTV / satellite TV list."""

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


DEFAULT_SOURCES = [
    "https://chaniug.github.io/IPTV-Collector/iptv-cn.m3u",
    "https://peterhchina.github.io/iptv/CNTV-V6.m3u",
    "https://raw.githubusercontent.com/best-fan/iptv-sources/main/cn_all.m3u8",
    "https://iptv-org.github.io/iptv/countries/cn.m3u",
]
MAX_BYTES = 8 * 1024 * 1024


def read_source(source):
    if urlparse(source).scheme in ("http", "https"):
        request = Request(source, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=15) as response:
            data = response.read(MAX_BYTES + 1)
    else:
        with open(source, "rb") as f:
            data = f.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("playlist exceeds 8 MiB")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("gb18030")


def channel_name(name):
    name = name.strip()
    cctv = re.search(r"CCTV\s*[-_ ]?\s*(\d{1,2})(\s*[+＋]|\s*[Kk])?", name, re.I)
    if cctv:
        number = int(cctv.group(1))
        suffix = (cctv.group(2) or "").strip().upper().replace("＋", "+")
        if not 1 <= number <= 17 or (suffix == "K" and number not in (4, 8)) or (suffix == "+" and number != 5):
            return None
        # The regional CCTV-4 feeds can show different programming.
        region = re.search(r"(?:asia|europe|america|亚洲|欧洲|美洲)", name, re.I)
        if number == 4 and region and not suffix:
            suffix = " " + {"asia": "亚洲", "europe": "欧洲", "america": "美洲"}.get(region.group().lower(), region.group())
        return f"CCTV-{number}{suffix}", "央视"
    satellite = re.search(r"([\u4e00-\u9fff]{2,5}卫视)", name)
    if satellite:
        return satellite.group(1), "卫视"
    return None


def parse_playlist(text):
    info = None
    directives = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("#EXTINF:"):
            info, directives = line, []
        elif info and line.startswith(("#EXTVLCOPT:", "#KODIPROP:")):
            directives.append(line)
        elif info and line and not line.startswith("#"):
            name = info.partition(",")[2].strip()
            channel = channel_name(name)
            if channel and urlparse(line.split("|", 1)[0]).scheme in ("http", "https", "rtsp", "rtmp", "udp", "rtp"):
                logo = re.search(r'tvg-logo="([^"]*)"', info, re.I)
                yield channel[0], channel[1], line, logo.group(1) if logo else "", tuple(directives)
            info, directives = None, []


def build_playlist(sources):
    channels = {}
    seen = set()
    for source in sources:
        try:
            text = read_source(source)
            if not text.lstrip().startswith("#EXTM3U"):
                raise ValueError("not an M3U playlist")
            count = 0
            for name, group, url, logo, directives in parse_playlist(text):
                count += 1
                key = (name, url, directives)
                if key not in seen:
                    channels.setdefault((name, group), []).append((url, logo, directives))
                    seen.add(key)
            print(f"读取成功: {source} ({count} 条央视/卫视线路)")
        except (OSError, UnicodeError, ValueError) as error:
            print(f"读取失败: {source}: {error}", file=sys.stderr)
    if not channels:
        raise ValueError("没有获得任何央视或卫视线路，未写入文件")
    lines = ["#EXTM3U"]
    for (name, group), streams in channels.items():
        for url, logo, directives in streams:
            lines.append(f'#EXTINF:-1 tvg-name="{name}" tvg-logo="{logo}" group-title="{group}",{name}')
            lines.extend(directives)
            lines.append(url)
    return "\n".join(lines) + "\n", len(channels), len(seen)


def main():
    parser = argparse.ArgumentParser(description="合并公开 M3U 中的央视和卫视频道")
    parser.add_argument("--source", action="append", help="M3U URL 或本地文件，可重复；指定后替换默认源")
    parser.add_argument("--output", default="playlist.m3u", help="输出路径（默认 playlist.m3u）")
    args = parser.parse_args()
    try:
        playlist, channel_count, stream_count = build_playlist(args.source or DEFAULT_SOURCES)
        Path(args.output).write_text(playlist, encoding="utf-8")
    except (OSError, ValueError) as error:
        parser.exit(1, f"错误: {error}\n")
    print(f"已生成 {args.output}: {channel_count} 个频道，{stream_count} 条去重线路。尚未验证实际播放。")


if __name__ == "__main__":
    main()
