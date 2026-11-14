#!/usr/bin/env python3
"""Filter credentials and reject unexpectedly small public playlists."""

import argparse
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit


def safe_entries(path):
    info, directives, entries = None, [], []
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if line.startswith("#EXTINF:"):
            info, directives = line, []
        elif info and line.startswith("#"):
            directives.append(line)
        elif info and line:
            url = urlsplit(line.split("|", 1)[0])
            names = [name.lower() for name, _ in parse_qsl(url.query, keep_blank_values=True)]
            sensitive = ("token", "secret", "password", "passwd", "session", "signature", "credential")
            has_secret = any(any(word in name for word in sensitive) or name in ("auth", "sign") for name in names)
            has_headers = "|" in line or any(
                word in directive.lower() for directive in directives
                for word in ("authorization", "cookie", "password", "token", "secret")
            )
            if url.scheme in ("http", "https") and url.hostname and not url.username and not url.password and not has_secret and not has_headers:
                entries.append((info, directives, line))
            info, directives = None, []
    return entries


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--previous", type=Path)
    args = parser.parse_args()
    entries = safe_entries(args.input)
    channels = {info.rsplit(",", 1)[-1] for info, _, _ in entries}
    previous = safe_entries(args.previous) if args.previous and args.previous.exists() else []
    previous_channels = {info.rsplit(",", 1)[-1] for info, _, _ in previous}
    if len(entries) < 30 or len(channels) < 20:
        parser.error(f"候选列表过小：{len(channels)} 个频道、{len(entries)} 条线路；保留旧版")
    if previous and (len(entries) < len(previous) * 0.5 or len(channels) < len(previous_channels) * 0.5):
        parser.error("候选列表不足旧版的一半；保留旧版")
    lines = ["#EXTM3U"]
    for info, directives, url in entries:
        lines.extend([info, *directives, url])
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"可发布：{len(channels)} 个频道，{len(entries)} 条线路")


if __name__ == "__main__":
    main()
