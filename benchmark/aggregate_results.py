#!/usr/bin/env python3

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "data" / "results"


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    rows_by_key = {}

    for result_file in RESULTS_DIR.glob("*/result.json"):
        run_dir = result_file.parent
        qc_file = run_dir / "qc.json"

        if not qc_file.exists():
            continue

        result = load_json(result_file)
        qc = load_json(qc_file)

        experiment = result.get(
            "experiment",
            result.get("run_id", run_dir.name),
        )

        model = result.get("model", {})
        model_name = model.get(
            "name",
            result.get("configuration", {}).get(
                "preset",
                "unknown",
            ),
        )

        stems = qc.get("stems", {})

        row = {
            "experiment": experiment,
            "model": model_name,
            "run_id": result.get("run_id", run_dir.name),
            "runtime_s": result["measurement"].get(
                "runtime_seconds"
            ),
            "rtf": result["measurement"].get("rtf"),
            "peak_ram_gib": round(
                result["measurement"].get(
                    "peak_ram_bytes",
                    0,
                ) / (1024 ** 3),
                2,
            ),
            "bass": stems.get("bass", {}).get("usability"),
            "drums": stems.get("drums", {}).get("usability"),
            "other": stems.get("other", {}).get("usability"),
            "vocals": stems.get("vocals", {}).get("usability"),
            "overall": qc.get("overall"),
            "mtime": result_file.stat().st_mtime,
        }

        key = (experiment, model_name)

        previous = rows_by_key.get(key)

        if (
            previous is None
            or row["mtime"] > previous["mtime"]
        ):
            rows_by_key[key] = row

    rows = sorted(
        rows_by_key.values(),
        key=lambda r: r["runtime_s"] or 999999,
    )

    if not rows:
        print("No runs with both result.json and qc.json found.")
        return

    headers = [
        "model",
        "runtime_s",
        "rtf",
        "peak_ram_gib",
        "bass",
        "drums",
        "other",
        "vocals",
        "overall",
    ]

    widths = {
        h: max(
            len(h),
            max(len(str(r.get(h, ""))) for r in rows),
        )
        for h in headers
    }

    print(
        "  ".join(
            h.ljust(widths[h])
            for h in headers
        )
    )

    print(
        "  ".join(
            "-" * widths[h]
            for h in headers
        )
    )

    for row in rows:
        print(
            "  ".join(
                str(row.get(h, "")).ljust(widths[h])
                for h in headers
            )
        )


if __name__ == "__main__":
    main()
