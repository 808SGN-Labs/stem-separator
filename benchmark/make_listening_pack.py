#!/usr/bin/env python3

import argparse
import json
import secrets
import shutil
import statistics
from pathlib import Path


RESULTS_DIR = Path("data/results")

EXPECTED_MODELS = {
    ("hdemucs_mmi.yaml", "4stems"),
    ("htdemucs.yaml", "balanced"),
    ("htdemucs_6s.yaml", "6stems"),
    ("htdemucs_ft.yaml", "maximum"),
    ("vocals_mel_band_roformer.ckpt", "vocals"),
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build a blind vocal listening pack from measured benchmark runs."
    )

    parser.add_argument(
        "--control",
        required=True,
        help="Control prefix, e.g. control-01 or control-02",
    )

    parser.add_argument(
        "--out",
        required=True,
        help="Output directory for the blind listening pack",
    )

    return parser.parse_args()


def experiment_names(control):
    return {
        f"{control}-hdemucs-mmi-001",
        f"{control}-htdemucs-001",
        f"{control}-htdemucs-6s-001",
        f"{control}-htdemucs-ft-001",
        f"{control}-mel-roformer-001",
    }


def load_results(control):
    rows = []
    allowed_experiments = experiment_names(control)

    for result_file in RESULTS_DIR.rglob("result.json"):
        try:
            data = json.loads(
                result_file.read_text(
                    encoding="utf-8"
                )
            )
        except Exception:
            continue

        if data.get("experiment") not in allowed_experiments:
            continue

        suite = data.get("benchmark_suite", {})

        if suite.get("role") != "measured":
            continue

        if not data.get("process", {}).get("success"):
            continue

        model_data = data.get("model", {})

        model = (
            model_data.get("resolved_name")
            or model_data.get("name")
        )

        preset = model_data.get("preset")

        runtime = (
            data.get("measurement", {})
            .get("end_to_end_seconds")
        )

        if (
            (model, preset) not in EXPECTED_MODELS
            or runtime is None
        ):
            continue

        rows.append({
            "result_file": result_file,
            "data": data,
            "model": model,
            "preset": preset,
            "runtime": float(runtime),
        })

    return rows


def choose_median_runs(rows):
    grouped = {}

    for row in rows:
        key = (
            row["model"],
            row["preset"],
        )

        grouped.setdefault(
            key,
            [],
        ).append(row)

    missing = (
        EXPECTED_MODELS
        - set(grouped.keys())
    )

    if missing:
        missing_text = ", ".join(
            f"{model}/{preset}"
            for model, preset in sorted(missing)
        )

        raise RuntimeError(
            "Missing measured benchmark results for: "
            f"{missing_text}"
        )

    selected = []

    for key in sorted(EXPECTED_MODELS):
        candidates = grouped[key]

        runtimes = sorted(
            row["runtime"]
            for row in candidates
        )

        median_runtime = statistics.median(
            runtimes
        )

        chosen = min(
            candidates,
            key=lambda row: (
                abs(
                    row["runtime"]
                    - median_runtime
                ),
                row["runtime"],
            ),
        )

        selected.append(chosen)

    return selected


def resolve_output_path(row, output):
    raw = output.get("path")

    if not raw:
        return None

    path = Path(raw)

    if path.is_absolute():
        return path

    candidates = [
        Path.cwd() / path,
        row["result_file"].parent / path,
        row["result_file"].parent / "stems" / path.name,
    ]

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    return Path.cwd() / path


def find_vocal_output(row):
    candidates = []

    for output in row["data"].get("outputs", []):
        path = resolve_output_path(
            row,
            output,
        )

        if path is None:
            continue

        name = path.name.lower()

        if (
            "_(vocals)_" in name
            or "_vocals.wav" in name
        ):
            candidates.append(path)

    unique = []

    seen = set()

    for path in candidates:
        key = str(path.resolve())

        if key not in seen:
            seen.add(key)
            unique.append(path)

    candidates = unique

    if len(candidates) != 1:
        print()
        print(
            f"DEBUG {row['data'].get('run_id', '-')}: "
            f"vocal candidates={len(candidates)}"
        )

        for output in row["data"].get("outputs", []):
            print(
                " ",
                output.get("path"),
            )

        raise RuntimeError(
            f"{row['data'].get('run_id', '-')}: "
            "expected exactly one vocal stem, "
            f"found {len(candidates)}"
        )

    path = candidates[0]

    if not path.is_file():
        raise FileNotFoundError(
            path
        )

    return path


def blind_order(selected):
    ordered = list(selected)

    secrets.SystemRandom().shuffle(
        ordered
    )

    return ordered


def make_score_template(control):
    return {
        "control": control,
        "instructions": {
            "scale": "1-5; higher is better",
            "do_not_open_mapping_until_finished": True,
        },
        "criteria": {
            "vocal_isolation": (
                "How little instrumental bleed remains"
            ),
            "vocal_integrity": (
                "How natural/intact the vocal sounds"
            ),
            "artifact_control": (
                "Absence of warble, metallic, watery "
                "or phase-like artifacts"
            ),
            "low_level_detail": (
                "Breaths, consonants, tails and quiet "
                "vocal information remain intact"
            ),
            "remix_usability": (
                "How usable this stem is in a real remix"
            ),
        },
        "scores": {},
    }


def clear_existing_pack(out_dir):
    if not out_dir.exists():
        return

    for name in [
        "A.wav",
        "B.wav",
        "C.wav",
        "D.wav",
        "E.wav",
        "scores.json",
        "mapping.secret.json",
    ]:
        path = out_dir / name

        if path.exists():
            path.unlink()


def main():
    args = parse_args()

    control = args.control.strip()
    out_dir = Path(args.out)

    if not control.startswith("control-"):
        raise RuntimeError(
            "--control must look like control-01 or control-02"
        )

    rows = load_results(
        control
    )

    if not rows:
        raise RuntimeError(
            f"No measured results found for {control}"
        )

    selected = choose_median_runs(
        rows
    )

    ordered = blind_order(
        selected
    )

    out_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    clear_existing_pack(
        out_dir
    )

    mapping = {}
    scores = make_score_template(
        control
    )

    labels = [
        chr(ord("A") + index)
        for index in range(len(ordered))
    ]

    for label, row in zip(
        labels,
        ordered,
    ):
        source = find_vocal_output(
            row
        )

        destination = (
            out_dir
            / f"{label}.wav"
        )

        shutil.copy2(
            source,
            destination,
        )

        mapping[label] = {
            "model": row["model"],
            "preset": row["preset"],
            "run_id": row["data"].get("run_id"),
            "runtime_seconds": row["runtime"],
            "source": str(source),
            "listening_file": str(destination),
        }

        scores["scores"][label] = {
            "vocal_isolation": None,
            "vocal_integrity": None,
            "artifact_control": None,
            "low_level_detail": None,
            "remix_usability": None,
            "notes": "",
        }

        print(
            f"Created {label}.wav"
        )

    secret_file = (
        out_dir
        / "mapping.secret.json"
    )

    secret_file.write_text(
        json.dumps(
            mapping,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    score_file = (
        out_dir
        / "scores.json"
    )

    score_file.write_text(
        json.dumps(
            scores,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print(
        f"Control:        {control}"
    )
    print(
        f"Listening pack: {out_dir}"
    )
    print(
        f"Score sheet:    {score_file}"
    )
    print(
        f"Secret mapping: {secret_file}"
    )
    print()
    print(
        "Listen to A.wav through E.wav."
    )
    print(
        "Do not open mapping.secret.json until scoring is done."
    )


if __name__ == "__main__":
    main()
