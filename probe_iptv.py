#!/usr/bin/env python3
"""Probe each M3U stream twice and retain streams with readable media both times."""

import argparse
import concurrent.futures
import ipaddress
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

TIMEOUT = 6
MAX_MANIFEST = 512 * 1024
SAMPLE_BYTES = 64 * 1024


def read(url, limit):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("不支持的协议")
    try:
        ip = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        ip = None
    if ip is not None and not ip.is_global:
        raise ValueError("非公网 IP，跳过")
    request = Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Accept": "*/*",
        "Range": f"bytes=0-{limit - 1}",
    })
    with urlopen(request, timeout=TIMEOUT) as response:
        return response.read(limit), response.geturl()


def media_format(data):
    # MPEG transport streams have a sync byte every 188 bytes. ISO BMFF
    # fragments carry one of these four-character box types near the start.
    for i in range(min(188, max(0, len(data) - 376))):
        if data[i] == data[i + 188] == data[i + 376] == 0x47:
            return "MPEG-TS"
    if len(data) >= 12 and data[4:8] in (b"ftyp", b"styp", b"moof", b"sidx"):
        return "MP4/fMP4"
    return None


def probe(url):
    start = time.monotonic()
    try:
        current = url.split("|", 1)[0]
        for depth in range(4):
            data, final_url = read(current, MAX_MANIFEST if depth == 0 else SAMPLE_BYTES)
            if data.lstrip().startswith(b"#EXTM3U"):
                text = data.decode("utf-8-sig", errors="replace")
                if "#EXT-X-KEY" in text and "METHOD=NONE" not in text:
                    return {"ok": False, "reason": "加密 HLS，未验证解密"}
                candidates = [line.strip() for line in text.splitlines()
                              if line.strip() and not line.lstrip().startswith("#")]
                if not candidates:
                    return {"ok": False, "reason": "HLS 清单没有媒体地址"}
                current = urljoin(final_url, candidates[0])
                continue
            media = media_format(data)
            if media:
                return {"ok": True, "format": media, "sample_bytes": len(data),
                        "elapsed_ms": round((time.monotonic() - start) * 1000)}
            return {"ok": False, "reason": "未识别为 MPEG-TS 或 MP4 分片"}
        return {"ok": False, "reason": "HLS 清单嵌套过深"}
    except HTTPError as error:
        return {"ok": False, "reason": f"HTTP {error.code}"}
    except Exception as error:
        return {"ok": False, "reason": f"{type(error).__name__}: {str(error)[:100]}"}


def read_playlist(path):
    entries = []
    info = None
    directives = []
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if line.startswith("#EXTINF:"):
            info, directives = line, []
        elif info and line.startswith("#"):
            directives.append(line)
        elif info and line:
            entries.append({"name": info.partition(",")[2], "info": info,
                            "directives": directives, "url": line})
            info = None
    return entries


def run_round(entries, indexes, workers, number):
    print(f"第 {number} 轮：检测 {len(indexes)} 条线路", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(probe, entries[i]["url"]): i for i in indexes}
        for count, future in enumerate(concurrent.futures.as_completed(futures), 1):
            entries[futures[future]].setdefault("checks", []).append(future.result())
            if count % 50 == 0 or count == len(indexes):
                print(f"第 {number} 轮进度 {count}/{len(indexes)}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="两次检查 M3U 各线路的媒体清单及分片")
    parser.add_argument("--input", default="playlist.m3u")
    parser.add_argument("--output", default="verified.m3u")
    parser.add_argument("--report", default="probe_report.json")
    parser.add_argument("--workers", type=int, default=48)
    args = parser.parse_args()
    entries = read_playlist(Path(args.input))
    if not entries:
        parser.error("输入列表没有频道")
    started = datetime.now(timezone.utc).isoformat()
    run_round(entries, range(len(entries)), max(1, min(args.workers, 64)), 1)
    candidates = [i for i, entry in enumerate(entries) if entry["checks"][0]["ok"]]
    print(f"初筛通过 {len(candidates)} 条，5 秒后再次检查", flush=True)
    time.sleep(5)
    run_round(entries, candidates, max(1, min(args.workers, 64)), 2)
    verified = [entry for entry in entries if len(entry["checks"]) == 2 and all(c["ok"] for c in entry["checks"])]
    output = ["#EXTM3U"]
    for entry in verified:
        output.extend([entry["info"], *entry["directives"], entry["url"]])
    Path(args.output).write_text("\n".join(output) + "\n", encoding="utf-8")
    report = {"started_utc": started, "finished_utc": datetime.now(timezone.utc).isoformat(),
              "description": "两次读取 HLS 清单及媒体片段或直连媒体样本；未解码画面、未测长期稳定性。",
              "total": len(entries), "first_pass": len(candidates), "both_pass": len(verified),
              "verified_channels": len({entry["name"] for entry in verified}), "entries": entries}
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"完成：{len(entries)} 条中 {len(verified)} 条通过两次检测，覆盖 {report['verified_channels']} 个频道。", flush=True)
    print("常见失败原因：", Counter(e['checks'][0].get('reason', '') for e in entries if not e['checks'][0]['ok']).most_common(8), flush=True)


if __name__ == "__main__":
    main()
