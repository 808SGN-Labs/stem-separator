#!/usr/bin/env python3

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmark" / "stemlab_benchmark.py"
RESULTS_DIR = ROOT / "data" / "results"


def latest_result_dir(before: set[Path]) -> Path:
    after = {p.parent for p in RESULTS_DIR.rglob("result.json")}
    new_dirs = sorted(after - before)

    if len(new_dirs) != 1:
        raise RuntimeError(
            f"Expected exactly one new result directory, got {len(new_dirs)}"
        )

    return new_dirs[0]


def tag_result(result_dir: Path, role: str, index: int) -> None:
    result_file = result_dir / "result.json"

    data = json.loads(
        result_file.read_text(encoding="utf-8")
    )

    data["benchmark_suite"] = {
        "role": role,
        "index": index,
    }

    result_file.write_text(
        json.dumps(data, indent=2) + "\n",
        encoding="utf-8",
    )


def run_once(config: Path, role: str, index: int) -> None:
    before = {
        p.parent
        for p in RESULTS_DIR.rglob("result.json")
    }

    print()
    print("=" * 80)
    print(f"{role.upper()} {index}")
    print("=" * 80)

    result = subprocess.run(
        [
            sys.executable,
            str(BENCHMARK),
            str(config),
        ],
        cwd=ROOT,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"{role} run {index} failed "
            f"with exit code {result.returncode}"
        )

    result_dir = latest_result_dir(before)

    tag_result(
        result_dir=result_dir,
        role=role,
        index=index,
    )

    print(f"Tagged: {result_dir.name} -> {role} #{index}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a StemLab benchmark suite with warm-up "
            "and measured repetitions."
        )
    )

    parser.add_argument(
        "config",
        type=Path,
        help="Benchmark config YAML",
    )

    parser.add_argument(
        "--warmup",
        type=int,
        default=1,
        help="Number of warm-up runs",
    )

    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of measured runs",
    )

    args = parser.parse_args()

    config = args.config

    if not config.is_absolute():
        config = ROOT / config

    config = config.resolve()

    if not config.is_file():
        print(
            f"ERROR: config not found: {config}",
            file=sys.stderr,
        )
        return 1

    if args.warmup < 0:
        print(
            "ERROR: --warmup must be >= 0",
            file=sys.stderr,
        )
        return 1

    if args.runs < 1:
        print(
            "ERROR: --runs must be >= 1",
            file=sys.stderr,
        )
        return 1

    print("StemLab benchmark suite")
    print(f"Config:   {config.relative_to(ROOT)}")
    print(f"Warm-up:  {args.warmup}")
    print(f"Measured: {args.runs}")

    try:
        for i in range(1, args.warmup + 1):
            run_once(
                config=config,
                role="warmup",
                index=i,
            )

        for i in range(1, args.runs + 1):
            run_once(
                config=config,
                role="measured",
                index=i,
            )

    except Exception as exc:
        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )
        return 1

    print()
    print("Suite complete.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())