#!/usr/bin/env python3
"""Decode a frame from twice-readable streams and retest the survivors."""

import argparse
import concurrent.futures
import json
import re
import subprocess
import time
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from probe_iptv import probe


def checkpoint(path, report):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def decode(ffmpeg, url):
    command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-threads", "1", "-rw_timeout", "7000000",
               "-user_agent", "Mozilla/5.0", "-i", url.split("|", 1)[0], "-map", "0:v:0",
               "-an", "-sn", "-dn", "-frames:v", "1", "-progress", "pipe:1", "-nostats", "-f", "null", "-"]
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=22)
        frames = re.findall(rb"(?:^|\n)frame=\s*(\d+)", result.stdout)
        if result.returncode == 0 and frames and max(map(int, frames)) >= 1:
            return {"ok": True, "frames": max(map(int, frames))}
        return {"ok": False, "reason": result.stderr.decode("utf-8", "replace")[-350:] or "未解码到视频帧"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "reason": "解码超时（22 秒）"}
    except OSError as error:
        return {"ok": False, "reason": str(error)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ffmpeg", required=True)
    p.add_argument("--report", default="probe_report.json")
    p.add_argument("--output", default="playable.m3u")
    args = p.parse_args()
    report_path = Path(args.report)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    entries = report["entries"]
    candidates = [e for e in entries if len(e["checks"]) == 2 and all(c["ok"] for c in e["checks"])]
    print(f"解码测试：{len(candidates)} 条候选线路", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        futures = {pool.submit(decode, args.ffmpeg, e["url"]): e for e in candidates}
        for count, future in enumerate(concurrent.futures.as_completed(futures), 1):
            futures[future]["decode"] = future.result()
            checkpoint(report_path, report)
            if count % 10 == 0 or count == len(candidates):
                print(f"解码进度 {count}/{len(candidates)}", flush=True)
    decoded = [e for e in candidates if e["decode"]["ok"]]
    report["decoded_frames"] = len(decoded)
    checkpoint(report_path, report)
    print(f"一帧解码成功 {len(decoded)} 条；至少间隔 30 秒进行末次媒体检查", flush=True)
    finished = datetime.fromisoformat(report["finished_utc"]).timestamp()
    time.sleep(max(0, 30 - (time.time() - finished)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:
        futures = {pool.submit(probe, e["url"]): e for e in decoded}
        for count, future in enumerate(concurrent.futures.as_completed(futures), 1):
            futures[future]["final_check"] = future.result()
            checkpoint(report_path, report)
            if count % 10 == 0 or count == len(decoded):
                print(f"末次检查 {count}/{len(decoded)}", flush=True)
    passed = [e for e in decoded if e["final_check"]["ok"]]
    groups = OrderedDict()
    for entry in passed:
        groups.setdefault(entry["name"], []).append(entry)
    output = ["#EXTM3U"]
    for group in groups.values():
        counts = {}
        remaining = list(group)
        while remaining and sum(counts.values()) < 5:
            index = min(range(len(remaining)), key=lambda i: counts.get(urlparse(remaining[i]["url"]).hostname, 0))
            entry = remaining.pop(index)
            host = urlparse(entry["url"]).hostname
            counts[host] = counts.get(host, 0) + 1
            output.extend([entry["info"], *entry["directives"], entry["url"]])
    Path(args.output).write_text("\n".join(output) + "\n", encoding="utf-8")
    report["final_pass"] = len(passed)
    report["final_channels"] = len(groups)
    report["exported_lines"] = sum(line.startswith("#EXTINF:") for line in output)
    report["final_finished_utc"] = datetime.now(timezone.utc).isoformat()
    checkpoint(report_path, report)
    print(f"完成：{len(groups)} 频道，{len(passed)} 条通过三次短时读取和一次视频帧解码。", flush=True)


if __name__ == "__main__":
    main()
