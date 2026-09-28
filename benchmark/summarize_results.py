#!/usr/bin/env python3

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path


def fmt_seconds(value):
    if value is None:
        return "-"
    return f"{value:.2f}s"


def fmt_rtf(value):
    if value is None:
        return "-"
    return f"{value:.3f}"


def fmt_ram_gib(bytes_value):
    if bytes_value is None:
        return "-"
    return f"{bytes_value / (1024 ** 3):.2f} GiB"


def get_nested(data, *keys):
    cur = data

    for key in keys:
        if not isinstance(cur, dict):
            return None

        cur = cur.get(key)

    return cur


def extract_control(experiment):
    if not experiment:
        return "-"

    parts = experiment.split("-")

    if len(parts) >= 2 and parts[0] == "control":
        return "-".join(parts[:2])

    return experiment


def load_results(root):
    rows = []
    issues = []

    for result_file in sorted(root.rglob("result.json")):
        try:
            data = json.loads(
                result_file.read_text(
                    encoding="utf-8"
                )
            )
        except Exception as exc:
            issues.append(
                (
                    result_file.parent.name,
                    f"invalid JSON: {exc}",
                )
            )
            continue

        run_id = (
            data.get("run_id")
            or result_file.parent.name
        )

        experiment = data.get("experiment")
        control = extract_control(experiment)

        model = (
            get_nested(
                data,
                "model",
                "resolved_name",
            )
            or get_nested(
                data,
                "model",
                "name",
            )
        )

        requested = (
            get_nested(
                data,
                "model",
                "requested_name",
            )
            or get_nested(
                data,
                "model",
                "name",
            )
        )

        preset = get_nested(
            data,
            "model",
            "preset",
        )

        role = get_nested(
            data,
            "benchmark_suite",
            "role",
        )

        suite_index = get_nested(
            data,
            "benchmark_suite",
            "index",
        )

        role_text = "-"

        if role:
            role_text = role

            if suite_index is not None:
                role_text = (
                    f"{role}:{suite_index}"
                )

        duration = (
            get_nested(
                data,
                "input",
                "duration_seconds",
            )
            or get_nested(
                data,
                "input",
                "excerpt_duration_seconds",
            )
            or 30.0
        )

        runtime = get_nested(
            data,
            "measurement",
            "end_to_end_seconds",
        )

        rtf = get_nested(
            data,
            "measurement",
            "rtf_end_to_end",
        )

        peak_rss = get_nested(
            data,
            "measurement",
            "peak_rss_bytes",
        )

        if peak_rss is None:
            peak_kib = get_nested(
                data,
                "measurement",
                "peak_rss_kib",
            )

            if peak_kib is not None:
                peak_rss = peak_kib * 1024

        success = get_nested(
            data,
            "process",
            "success",
        )

        outputs = data.get("outputs", [])

        if isinstance(outputs, list):
            stems = len(outputs)
        else:
            stems = None

        rows.append({
            "run_id": run_id,
            "experiment": experiment,
            "control": control,
            "model": model,
            "requested": requested,
            "preset": preset,
            "role": role,
            "role_text": role_text,
            "suite_index": suite_index,
            "stems": stems,
            "duration": duration,
            "runtime": runtime,
            "rtf": rtf,
            "peak_rss": peak_rss,
            "success": success,
            "result_file": result_file,
        })

        checks = [
            (
                model,
                "model.name/resolved_name",
            ),
            (
                requested,
                "model.requested_name/name",
            ),
            (
                preset,
                "model.preset",
            ),
            (
                runtime,
                "measurement.end_to_end_seconds",
            ),
            (
                rtf,
                "measurement.rtf_end_to_end",
            ),
        ]

        for value, field in checks:
            if value is None:
                issues.append(
                    (
                        run_id,
                        f"missing {field}",
                    )
                )

    return rows, issues


def print_raw(rows):
    headers = [
        "RUN",
        "CONTROL",
        "MODEL",
        "REQUESTED",
        "PRESET",
        "ROLE",
        "STEMS",
        "AUDIO",
        "TIME",
        "RTF",
        "RAM",
        "OK",
    ]

    table = []

    for row in rows:
        table.append([
            row["run_id"],
            row["control"],
            row["model"] or "-",
            row["requested"] or "-",
            row["preset"] or "-",
            row["role_text"],
            (
                str(row["stems"])
                if row["stems"] is not None
                else "-"
            ),
            fmt_seconds(
                float(row["duration"])
                if row["duration"] is not None
                else None
            ),
            fmt_seconds(row["runtime"]),
            fmt_rtf(row["rtf"]),
            fmt_ram_gib(row["peak_rss"]),
            (
                "YES"
                if row["success"]
                else "NO"
            ),
        ])

    widths = [
        max(
            len(headers[i]),
            max(
                (
                    len(str(r[i]))
                    for r in table
                ),
                default=0,
            ),
        )
        for i in range(len(headers))
    ]

    print(
        "  ".join(
            headers[i].ljust(widths[i])
            for i in range(len(headers))
        )
    )

    print(
        "  ".join(
            "-" * widths[i]
            for i in range(len(headers))
        )
    )

    for row in table:
        print(
            "  ".join(
                str(row[i]).ljust(widths[i])
                for i in range(len(headers))
            )
        )


def measured_rows(rows):
    return [
        row
        for row in rows
        if (
            row["role"] == "measured"
            and row["success"]
            and row["runtime"] is not None
            and row["rtf"] is not None
            and row["model"]
            and row["preset"]
        )
    ]


def summarize_group(group):
    runtimes = [
        row["runtime"]
        for row in group
    ]

    rtfs = [
        row["rtf"]
        for row in group
    ]

    ram = [
        row["peak_rss"]
        for row in group
        if row["peak_rss"] is not None
    ]

    return {
        "n": len(group),
        "median": statistics.median(
            runtimes
        ),
        "min": min(runtimes),
        "max": max(runtimes),
        "median_rtf": statistics.median(
            rtfs
        ),
        "peak_ram": (
            max(ram)
            if ram
            else None
        ),
    }


def print_summary(
    title,
    grouped,
    include_control,
):
    print()
    print(title)
    print()

    if include_control:
        headers = [
            "CONTROL",
            "MODEL",
            "PRESET",
            "N",
            "MEDIAN",
            "MIN",
            "MAX",
            "MEDIAN RTF",
            "PEAK RAM",
        ]
    else:
        headers = [
            "MODEL",
            "PRESET",
            "N",
            "MEDIAN",
            "MIN",
            "MAX",
            "MEDIAN RTF",
            "PEAK RAM",
        ]

    table = []

    for key in sorted(grouped):
        stats = summarize_group(
            grouped[key]
        )

        if include_control:
            control, model, preset = key

            row = [
                control,
                model,
                preset,
            ]
        else:
            model, preset = key

            row = [
                model,
                preset,
            ]

        row.extend([
            str(stats["n"]),
            fmt_seconds(stats["median"]),
            fmt_seconds(stats["min"]),
            fmt_seconds(stats["max"]),
            fmt_rtf(stats["median_rtf"]),
            fmt_ram_gib(stats["peak_ram"]),
        ])

        table.append(row)

    widths = [
        max(
            len(headers[i]),
            max(
                (
                    len(str(r[i]))
                    for r in table
                ),
                default=0,
            ),
        )
        for i in range(len(headers))
    ]

    print(
        "  ".join(
            headers[i].ljust(widths[i])
            for i in range(len(headers))
        )
    )

    print(
        "  ".join(
            "-" * widths[i]
            for i in range(len(headers))
        )
    )

    for row in table:
        print(
            "  ".join(
                str(row[i]).ljust(widths[i])
                for i in range(len(headers))
            )
        )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "results_dir",
        nargs="?",
        default="data/results",
    )

    args = parser.parse_args()

    root = Path(args.results_dir)

    rows, issues = load_results(root)

    print(
        f"Found {len(rows)} benchmark result(s)"
    )
    print()

    print_raw(rows)

    measured = measured_rows(rows)

    per_control = defaultdict(list)
    aggregate = defaultdict(list)

    for row in measured:
        per_control[
            (
                row["control"],
                row["model"],
                row["preset"],
            )
        ].append(row)

        aggregate[
            (
                row["model"],
                row["preset"],
            )
        ].append(row)

    print_summary(
        "Official measured benchmark summary by control",
        per_control,
        include_control=True,
    )

    print_summary(
        "Aggregate measured benchmark summary across controls",
        aggregate,
        include_control=False,
    )

    if issues:
        print()
        print("Schema issues:")

        for run_id, issue in issues:
            print(
                f"WARN  {run_id}: {issue}"
            )


if __name__ == "__main__":
    main()
