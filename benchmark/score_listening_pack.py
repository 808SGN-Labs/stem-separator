#!/usr/bin/env python3

import json
from pathlib import Path


PACK = Path(
    "data/listening/control-01-vocals-blind-02"
)

SCORES = PACK / "scores.json"

CRITERIA = [
    "vocal_isolation",
    "vocal_integrity",
    "artifact_control",
    "low_level_detail",
    "remix_usability",
]


def ask_score(label, criterion, current):
    while True:
        prompt = (
            f"{label} | {criterion}"
            f" [{current if current is not None else '-'}]: "
        )

        value = input(prompt).strip()

        if value == "":
            return current

        try:
            score = int(value)
        except ValueError:
            print("Enter 1-5.")
            continue

        if 1 <= score <= 5:
            return score

        print("Enter 1-5.")


def main():
    data = json.loads(
        SCORES.read_text(encoding="utf-8")
    )

    print()
    print("StemLab blind vocal evaluation")
    print("Scale: 1 = poor, 5 = excellent")
    print("Press Enter to keep an existing value.")
    print()

    for label in sorted(data["scores"]):
        print("=" * 60)
        print(f"{label}.wav")
        print("=" * 60)

        row = data["scores"][label]

        for criterion in CRITERIA:
            row[criterion] = ask_score(
                label,
                criterion,
                row.get(criterion),
            )

        print()
        current_note = row.get("notes", "")

        print(
            f"Notes"
            f" [{current_note if current_note else '-'}]:"
        )

        note = input("> ").strip()

        if note:
            row["notes"] = note

        SCORES.write_text(
            json.dumps(
                data,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        print()

    print("=" * 60)
    print("Saved:", SCORES)
    print("=" * 60)

    print()
    print("Scores:")
    print()

    for label, row in sorted(
        data["scores"].items()
    ):
        values = [
            row.get(k)
            for k in CRITERIA
            if isinstance(row.get(k), (int, float))
        ]

        avg = (
            sum(values) / len(values)
            if values
            else None
        )

        avg_text = (
            f"{avg:.2f}"
            if avg is not None
            else "-"
        )

        print(
            f"{label}: "
            f"average={avg_text} "
            f"notes={row.get('notes', '')}"
        )


if __name__ == "__main__":
    main()
