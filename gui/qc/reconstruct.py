#!/usr/bin/env python3

import subprocess
from pathlib import Path


def build_reconstruction(stems: dict[str, Path], output: Path) -> Path:
    """
    Sum all supplied separated stems into a float WAV reconstruction.

    The reconstruction keeps the separator's native sample rate and is used
    only for QC/auditioning. The original source file is never modified.
    """

    if not stems:
        raise ValueError("Cannot build RECON; no stems supplied")

    ordered = []
    for name in sorted(stems):
        path = Path(stems[name])
        if not path.is_file():
            raise FileNotFoundError(f"Missing stem '{name}': {path}")
        ordered.append((name, path))

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    inputs = []
    for _, path in ordered:
        inputs.extend(["-i", str(path)])

    labels = "".join(f"[{i}:a]" for i in range(len(ordered)))
    filter_complex = (
        f"{labels}amix=inputs={len(ordered)}:"
        "duration=longest:normalize=0[a]"
    )

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[a]",
        "-c:a", "pcm_f32le",
        str(output),
    ]

    subprocess.run(cmd, check=True)
    return output


if __name__ == "__main__":
    raise SystemExit(
        "This module is used by StemLab QC; run gui/qc/app.py."
    )
