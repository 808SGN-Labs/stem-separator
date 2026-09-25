#!/usr/bin/env python3

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEPARATOR = ROOT / "scripts" / "stem-separate"
RESULTS_DIR = ROOT / "data" / "results"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def audio_info(path: Path) -> dict:
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "a:0",
        "-show_entries",
        "stream=codec_name,sample_rate,channels:format=duration",
        "-of", "json",
        str(path),
    ]

    result = subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
    )

    data = json.loads(result.stdout)
    stream = data["streams"][0]
    fmt = data["format"]

    return {
        "codec": stream.get("codec_name"),
        "sample_rate": int(stream["sample_rate"]),
        "channels": int(stream["channels"]),
        "duration_seconds": float(fmt["duration"]),
    }


def cpu_model() -> str | None:
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return None


def total_ram_bytes() -> int | None:
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    kib = int(line.split()[1])
                    return kib * 1024
    except OSError:
        pass
    return None


def environment_info() -> dict:
    return {
        "platform": platform.platform(),
        "system": platform.system(),
        "kernel": platform.release(),
        "machine": platform.machine(),
        "cpu": cpu_model(),
        "logical_cpus": os.cpu_count(),
        "ram_bytes": total_ram_bytes(),
        "python": platform.python_version(),
    }


def run_benchmark(preset: str, input_path: Path) -> dict:
    input_path = input_path.resolve()

    if not input_path.is_file():
        raise FileNotFoundError(f"Input not found: {input_path}")

    if not SEPARATOR.is_file():
        raise FileNotFoundError(f"StemLab CLI not found: {SEPARATOR}")

    if shutil.which("ffprobe") is None:
        raise RuntimeError("ffprobe not found")

    time_binary = shutil.which("time")
    if time_binary is None:
        raise RuntimeError("/usr/bin/time not found")

    info = audio_info(input_path)
    input_hash = sha256(input_path)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{timestamp}-{preset}-{input_hash[:8]}"

    output_dir = RESULTS_DIR / run_id / "stems"
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w+",
        prefix="stemlab-time-",
        suffix=".txt",
        delete=False,
    ) as tf:
        time_file = Path(tf.name)

    command = [
        time_binary,
        "-f",
        "%e\n%M",
        "-o",
        str(time_file),
        str(SEPARATOR),
        preset,
        str(input_path),
        str(output_dir),
    ]

    started_utc = datetime.now(timezone.utc).isoformat()
    start = time.perf_counter()

    process = subprocess.run(command)

    elapsed_python = time.perf_counter() - start
    finished_utc = datetime.now(timezone.utc).isoformat()

    try:
        timing = time_file.read_text().strip().splitlines()
    finally:
        time_file.unlink(missing_ok=True)

    runtime_seconds = (
        float(timing[0])
        if len(timing) >= 1
        else elapsed_python
    )

    peak_ram_kib = (
        int(timing[1])
        if len(timing) >= 2
        else None
    )

    output_files = []

    if output_dir.exists():
        for path in sorted(output_dir.rglob("*")):
            if path.is_file():
                output_files.append({
                    "path": str(path.relative_to(ROOT)),
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                })

    duration = info["duration_seconds"]

    result = {
        "schema_version": 1,
        "run_id": run_id,
        "started_utc": started_utc,
        "finished_utc": finished_utc,

        "input": {
            "path": str(input_path),
            "sha256": input_hash,
            **info,
        },

        "configuration": {
            "preset": preset,
        },

        "environment": environment_info(),

        "measurement": {
            "runtime_seconds": runtime_seconds,
            "python_wall_seconds": elapsed_python,
            "rtf": runtime_seconds / duration if duration > 0 else None,
            "peak_ram_kib": peak_ram_kib,
            "peak_ram_bytes": (
                peak_ram_kib * 1024
                if peak_ram_kib is not None
                else None
            ),
        },

        "process": {
            "exit_code": process.returncode,
            "success": process.returncode == 0,
        },

        "outputs": output_files,
    }

    result_dir = RESULTS_DIR / run_id
    result_file = result_dir / "result.json"

    result_file.write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
    )

    return result


def main():
    parser = argparse.ArgumentParser(
        description="StemLab reproducible benchmark runner"
    )

    parser.add_argument(
        "preset",
        help="StemLab preset, e.g. balanced",
    )

    parser.add_argument(
        "input",
        type=Path,
        help="Input audio file",
    )

    args = parser.parse_args()

    try:
        result = run_benchmark(args.preset, args.input)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print()
    print("StemLab benchmark complete")
    print(f"Run:      {result['run_id']}")
    print(f"Runtime:  {result['measurement']['runtime_seconds']:.2f} s")
    print(f"RTF:      {result['measurement']['rtf']:.3f}")
    print(
        f"Peak RAM: "
        f"{result['measurement']['peak_ram_bytes'] / (1024**3):.2f} GiB"
    )
    print(f"Outputs:  {len(result['outputs'])}")
    print(
        f"Result:   data/results/{result['run_id']}/result.json"
    )

    return 0 if result["process"]["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
