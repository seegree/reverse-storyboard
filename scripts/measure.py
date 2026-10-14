"""Measure elapsed time and sampled process-tree RSS for a real CLI invocation."""
import argparse
import json
from pathlib import Path
import subprocess
import time

import psutil

parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("command", nargs=argparse.REMAINDER)
args = parser.parse_args()
command = args.command[1:] if args.command[:1] == ["--"] else args.command
started = time.perf_counter()
proc = subprocess.Popen(command)
parent = psutil.Process(proc.pid)
peak = 0
memory_available = True
while proc.poll() is None:
    try:
        if not memory_available:
            time.sleep(0.02)
            continue
        total = 0
        for child in [parent] + parent.children(recursive=True):
            try:
                total += child.memory_info().rss
            except psutil.NoSuchProcess:
                pass
        peak = max(peak, total)
    except psutil.NoSuchProcess:
        pass
    except (psutil.AccessDenied, PermissionError):
        memory_available = False
    time.sleep(0.02)
record = {"command": command, "elapsed_seconds": time.perf_counter() - started,
          "peak_process_tree_rss_mib": peak / (1024 * 1024) if memory_available else None, "exit_code": proc.returncode,
          "note": "RSS sampled every 20 ms, summed across parent and children; shared pages may be counted twice."}
args.output.write_text(json.dumps(record, indent=2), encoding="utf-8")
print(json.dumps(record, indent=2))
raise SystemExit(proc.returncode)
