#!/usr/bin/env python3

import argparse
import json
import secrets
import shutil
import statistics
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "data" / "results"
LISTENING_DIR = ROOT / "data" / "listening"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build a randomized StemLab blind listening pack."
    )
    parser.add_argument(
        "--control",
        required=True,
        help="Control id, e.g. control-03",
    )
    parser.add_argument(
        "--stem",
        choices=("vocals", "bass", "drums", "other"),
        default="vocals",
        help="Stem to compare. Models without this stem are excluded.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="Output directory. Defaults to data/listening/<control>-<stem>-blind-01",
    )
    return parser.parse_args()


def resolved_model(data):
    model = data.get("model", {})
    return (
        model.get("resolved_name")
        or model.get("name")
        or model.get("requested_name")
        or "unknown"
    )


def requested_model(data):
    model = data.get("model", {})
    return (
        model.get("requested_name")
        or model.get("name")
        or model.get("resolved_name")
        or "unknown"
    )


def output_path(result_file: Path, output: dict) -> Path | None:
    raw = output.get("path")
    if not raw:
        return None

    path = Path(raw)
    if path.is_absolute():
        return path

    # Benchmark result paths are normally repository-relative.
    candidate = ROOT / path
    if candidate.is_file():
        return candidate

    # Defensive fallback for older result.json layouts.
    candidate = result_file.parent / path
    if candidate.is_file():
        return candidate

    return ROOT / path


def stem_matches(path: Path, stem: str) -> bool:
    name = path.name.lower()
    singular = stem.lower()

    patterns = {
        "vocals": ("(vocals)", "_(vocals)_", "_vocals.wav"),
        "bass": ("(bass)", "_(bass)_", "_bass.wav"),
        "drums": ("(drums)", "_(drums)_", "_drums.wav"),
        "other": ("(other)", "_(other)_", "_other.wav"),
    }[singular]

    return any(token in name for token in patterns)


def find_stem_output(result_file: Path, data: dict, stem: str) -> Path | None:
    matches = []

    for output in data.get("outputs", []):
        path = output_path(result_file, output)
        if path is None:
            continue
        if stem_matches(path, stem):
            matches.append(path)

    # Exactly one target stem is required. A model that does not produce the
    # requested stem is simply ineligible for this blind pack.
    if len(matches) != 1:
        return None

    path = matches[0]
    if not path.is_file():
        return None

    return path


def load_eligible_results(control: str, stem: str):
    rows = []

    for result_file in RESULTS_DIR.rglob("result.json"):
        try:
            data = json.loads(result_file.read_text(encoding="utf-8"))
        except Exception:
            continue

        experiment = str(data.get("experiment", ""))
        run_id = str(data.get("run_id", result_file.parent.name))

        if not (
            experiment.startswith(control + "-")
            or f"-{control}-" in run_id
        ):
            continue

        if data.get("benchmark_suite", {}).get("role") != "measured":
            continue

        if not data.get("process", {}).get("success", False):
            continue

        runtime = data.get("measurement", {}).get("end_to_end_seconds")
        if runtime is None:
            continue

        stem_path = find_stem_output(result_file, data, stem)
        if stem_path is None:
            continue

        rows.append(
            {
                "result_file": result_file,
                "data": data,
                "model": resolved_model(data),
                "requested_model": requested_model(data),
                "preset": data.get("model", {}).get("preset", "-"),
                "runtime": float(runtime),
                "stem_path": stem_path,
            }
        )

    return rows


def choose_representative_runs(rows):
    """Choose one measured run per resolved model/preset, nearest its median runtime."""
    grouped = {}

    for row in rows:
        key = (row["model"], row["preset"])
        grouped.setdefault(key, []).append(row)

    selected = []

    for key, group in grouped.items():
        runtimes = [row["runtime"] for row in group]
        median = statistics.median(runtimes)

        chosen = min(
            group,
            key=lambda row: (
                abs(row["runtime"] - median),
                row["runtime"],
                row["data"].get("run_id", ""),
            ),
        )
        selected.append(chosen)

    # Stable pre-shuffle order makes debugging easier. Blind order is randomized later.
    selected.sort(key=lambda row: (row["model"], row["preset"]))
    return selected


def randomized_order(rows):
    ordered = list(rows)
    secrets.SystemRandom().shuffle(ordered)
    return ordered


def criteria_for(stem: str):
    if stem == "other":
        return {
            "other_isolation": "How little vocal, drum and bass bleed remains",
            "harmonic_integrity": "How intact melodic and harmonic tone remains",
            "artifact_control": "Absence of warble and metallic artifacts",
            "tail_integrity": "Natural reverb, ambience and sustained note tails",
            "remix_usability": "How usable this music stem is in a real remix",
        }
    if stem == "drums":
        return {
            "drum_isolation": "How little melodic, vocal or other non-drum bleed remains",
            "transient_integrity": "Snare punch, attack and reverb tail remain intact",
            "cymbal_integrity": "Natural hats/cymbals and decay without watery artifacts",
            "kick_integrity": "Kick sub weight, body, punch and decay remain intact",
            "remix_usability": "How usable this drum stem is in a real remix",
        }
    if stem == "bass":
        return {
            "bass_isolation": "How little kick, drums, vocals or other mix bleed remains",
            "bass_integrity": "How intact the bass tone, envelope and sustain remain",
            "low_end_stability": "Absence of sub holes, phase instability or low-end wobble",
            "note_definition": "How clearly attacks, pitches and note changes remain defined",
            "remix_usability": "How usable this bass stem is in a real remix",
        }

    return {
        "vocal_isolation": "How little instrumental bleed remains",
        "vocal_integrity": "How natural/intact the vocal sounds",
        "artifact_control": "Absence of warble, metallic, watery or phase-like artifacts",
        "low_level_detail": "Breaths, consonants, tails and quiet vocal information remain intact",
        "remix_usability": "How usable this stem is in a real remix",
    }


def main():
    args = parse_args()

    control = args.control.strip()
    stem = args.stem
    out_dir = args.out or (LISTENING_DIR / f"{control}-{stem}-blind-01")
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir

    eligible = load_eligible_results(control, stem)
    selected = choose_representative_runs(eligible)

    if len(selected) < 2:
        raise SystemExit(
            f"ERROR: only {len(selected)} model(s) produced a usable {stem} stem for {control}"
        )

    if len(selected) > 5:
        raise SystemExit("ERROR: QC UI supports at most 5 candidates per pack")

    # Never destroy a previous randomization or its listening scores.
    if out_dir.exists() and any(out_dir.iterdir()):
        raise SystemExit(f"ERROR: pack already exists; use a new --out directory: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)

    ordered = randomized_order(selected)
    mapping = {}
    scores = {}
    criteria = criteria_for(stem)

    for index, row in enumerate(ordered):
        label = chr(ord("A") + index)
        destination = out_dir / f"{label}.wav"
        shutil.copy2(row["stem_path"], destination)

        mapping[label] = {
            "model": row["model"],
            "requested_model": row["requested_model"],
            "preset": row["preset"],
            "run_id": row["data"].get("run_id", row["result_file"].parent.name),
            "runtime_seconds": row["runtime"],
            "stem": stem,
            "source": str(row["stem_path"]),
            "listening_file": str(destination.relative_to(ROOT)),
        }

        scores[label] = {key: None for key in criteria}
        scores[label]["notes"] = ""

        print(f"Created {label}.wav")

    mapping_file = out_dir / "mapping.secret.json"
    score_file = out_dir / "scores.json"

    mapping_file.write_text(
        json.dumps(mapping, indent=2) + "\n",
        encoding="utf-8",
    )

    payload = {
        "control": control,
        "blind_type": "vocal" if stem == "vocals" else stem,
        "stem": stem,
        "candidate_count": len(ordered),
        "instructions": {
            "scale": "1-5; higher is better",
            "anchors": {"1": "Poor", "3": "Acceptable", "5": "Excellent"},
            "do_not_open_mapping_until_finished": True,
        },
        "criteria": criteria,
        "scores": scores,
    }

    score_file.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )


    print()
    print(f"Control:        {control}")
    print(f"Stem:           {stem}")
    print(f"Candidates:     {len(ordered)}")
    print(f"Listening pack: {out_dir.relative_to(ROOT)}")
    print(f"Score sheet:    {score_file.relative_to(ROOT)}")
    print(f"Secret mapping: {mapping_file.relative_to(ROOT)}")
    print()
    print("Eligible models:")
    for row in selected:
        print(f"  - {row['model']} [{row['preset']}]")
    print()
    print(f"Listen to A.wav through {chr(ord('A') + len(ordered) - 1)}.wav.")
    print("Do not open mapping.secret.json until scoring is done.")


if __name__ == "__main__":
    main()
