#!/usr/bin/env python3

import argparse
import hashlib
import json
import os
import platform
import re
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

DEFAULT_VENV = Path(
    os.environ.get(
        "XDG_DATA_HOME",
        str(Path.home() / ".local/share"),
    )
) / "808sgn-stem-lab" / ".venv"

LEGACY_VENV = Path.home() / "audio-separator" / ".venv"

MODELS_DIR = Path(
    os.environ.get(
        "STEM_LAB_MODELS",
        str(
            Path(
                os.environ.get(
                    "XDG_CACHE_HOME",
                    str(Path.home() / ".cache"),
                )
            )
            / "808sgn-stem-lab"
            / "models"
        ),
    )
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def parse_scalar(value: str):
    value = value.strip()

    if (
        len(value) >= 2
        and value[0] == value[-1]
        and value[0] in ("'", '"')
    ):
        return value[1:-1]

    lower = value.lower()

    if lower == "true":
        return True

    if lower == "false":
        return False

    if lower in ("null", "none"):
        return None

    try:
        if "." in value:
            return float(value)

        return int(value)

    except ValueError:
        return value


def load_simple_yaml(path: Path) -> dict:
    """
    Minimal YAML reader for StemLab benchmark configs.

    Supports:
      key: value
      nested mappings by indentation

    Lists and advanced YAML syntax are intentionally unsupported.
    """

    root = {}
    stack = [(-1, root)]

    for line_no, raw in enumerate(
        path.read_text(
            encoding="utf-8"
        ).splitlines(),
        start=1,
    ):
        if (
            not raw.strip()
            or raw.lstrip().startswith("#")
        ):
            continue

        indent = len(raw) - len(raw.lstrip(" "))
        text = raw.strip()

        if ":" not in text:
            raise ValueError(
                f"{path}:{line_no}: unsupported YAML syntax"
            )

        key, value = text.split(":", 1)

        key = key.strip()
        value = value.strip()

        while (
            stack
            and indent <= stack[-1][0]
        ):
            stack.pop()

        if not stack:
            raise ValueError(
                f"{path}:{line_no}: invalid indentation"
            )

        parent = stack[-1][1]

        if value == "":
            child = {}
            parent[key] = child
            stack.append(
                (
                    indent,
                    child,
                )
            )

        else:
            parent[key] = parse_scalar(value)

    return root


def audio_info(path: Path) -> dict:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        (
            "stream="
            "codec_name,"
            "sample_rate,"
            "channels,"
            "bits_per_sample:"
            "format=duration"
        ),
        "-of",
        "json",
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

    bits = stream.get(
        "bits_per_sample"
    )

    return {
        "codec": stream.get(
            "codec_name"
        ),
        "sample_rate": int(
            stream["sample_rate"]
        ),
        "channels": int(
            stream["channels"]
        ),
        "bits_per_sample": (
            int(bits)
            if bits
            else None
        ),
        "duration_seconds": float(
            fmt["duration"]
        ),
    }


def cpu_model():
    try:
        with open(
            "/proc/cpuinfo",
            encoding="utf-8",
        ) as f:
            for line in f:
                if line.startswith(
                    "model name"
                ):
                    return (
                        line.split(
                            ":",
                            1,
                        )[1]
                        .strip()
                    )

    except OSError:
        pass

    return None


def total_ram_bytes():
    try:
        with open(
            "/proc/meminfo",
            encoding="utf-8",
        ) as f:
            for line in f:
                if line.startswith(
                    "MemTotal:"
                ):
                    return (
                        int(
                            line.split()[1]
                        )
                        * 1024
                    )

    except OSError:
        pass

    return None


def resolve_separator_venv() -> Path:
    override = os.environ.get(
        "STEM_LAB_VENV"
    )

    if override:
        return Path(
            override
        ).expanduser()

    if (
        DEFAULT_VENV
        / "bin/audio-separator"
    ).is_file():
        return DEFAULT_VENV

    if (
        LEGACY_VENV
        / "bin/audio-separator"
    ).is_file():
        return LEGACY_VENV

    return DEFAULT_VENV


def command_output(cmd):
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )

        return (
            result.stdout
            or result.stderr
        ).strip()

    except Exception:
        return None


def first_line(value):
    if not value:
        return None

    return value.splitlines()[0].strip()


def software_info() -> dict:
    venv = resolve_separator_venv()

    separator_python = (
        venv / "bin/python"
    )

    separator_binary = (
        venv / "bin/audio-separator"
    )

    return {
        "benchmark_python": {
            "version":
                platform.python_version(),
            "executable":
                sys.executable,
        },
        "separator_python": {
            "version": first_line(
                command_output(
                    [
                        str(
                            separator_python
                        ),
                        "--version",
                    ]
                )
            ),
            "executable": str(
                separator_python
            ),
        },
        "audio_separator": {
            "version": first_line(
                command_output(
                    [
                        str(
                            separator_binary
                        ),
                        "--version",
                    ]
                )
            ),
            "executable": str(
                separator_binary
            ),
        },
        "ffmpeg": {
            "version": first_line(
                command_output(
                    [
                        "ffmpeg",
                        "-version",
                    ]
                )
            ),
        },
    }


def environment_info() -> dict:
    return {
        "platform":
            platform.platform(),
        "system":
            platform.system(),
        "kernel":
            platform.release(),
        "machine":
            platform.machine(),
        "cpu":
            cpu_model(),
        "logical_cpus":
            os.cpu_count(),
        "ram_bytes":
            total_ram_bytes(),
    }


def model_provenance(
    model_name: str,
) -> dict:
    descriptor = (
        MODELS_DIR
        / model_name
    )

    result = {
        "model_dir":
            str(MODELS_DIR),
        "descriptor":
            None,
        "artifacts":
            [],
    }

    if not descriptor.is_file():
        return result

    result["descriptor"] = {
        "filename":
            descriptor.name,
        "bytes":
            descriptor.stat().st_size,
        "sha256":
            sha256(descriptor),
    }

    # Demucs descriptors are text YAML files.
    # Binary ckpt/onnx/pth models cannot be decoded as text.
    if descriptor.suffix.lower() in {
        ".ckpt",
        ".onnx",
        ".pth",
        ".pt",
    }:
        return result

    text = descriptor.read_text(
        encoding="utf-8",
        errors="replace",
    )

    match = re.search(
        (
            r"models\s*:\s*"
            r"\[\s*['\"]"
            r"([^'\"]+)"
            r"['\"]"
        ),
        text,
    )

    if not match:
        return result

    model_id = match.group(1)

    candidates = sorted(
        MODELS_DIR.glob(
            f"{model_id}-*.th"
        )
    )

    for artifact in candidates:
        result["artifacts"].append(
            {
                "model_id":
                    model_id,
                "filename":
                    artifact.name,
                "bytes":
                    artifact.stat().st_size,
                "sha256":
                    sha256(artifact),
            }
        )

    return result


def validate_config(
    config: dict,
):
    required = [
        ("experiment",),
        ("input", "path"),
        ("input", "sha256"),
        ("model", "engine"),
        ("model", "preset"),
        ("model", "name"),
    ]

    for keys in required:
        value = config

        for key in keys:
            if (
                not isinstance(
                    value,
                    dict,
                )
                or key not in value
            ):
                raise ValueError(
                    "Missing config field: "
                    + ".".join(keys)
                )

            value = value[key]


def parse_resolved_model(
    output: str,
) -> str | None:
    """
    Preferred machine-readable marker:

        STEMLAB_RESOLVED_MODEL=<filename>

    Fallback:
        Parse audio-separator's
        "Loading model <filename>..."
        log line.
    """

    prefix = (
        "STEMLAB_RESOLVED_MODEL="
    )

    for line in output.splitlines():
        stripped = line.strip()

        if stripped.startswith(prefix):
            value = stripped[
                len(prefix):
            ].strip()

            if value:
                return value

    pattern = re.compile(
        r"Loading model\s+(.+?)\.\.\."
    )

    for line in output.splitlines():
        match = pattern.search(line)

        if match:
            value = (
                match.group(1)
                .strip()
            )

            if value:
                return value

    return None


def parse_time_file(
    path: Path,
    python_wall: float,
) -> tuple[float, int | None]:
    """
    Parse GNU /usr/bin/time output safely.

    Expected successful format:

        <elapsed seconds>
        <peak RSS KiB>

    GNU time can append text on command failure,
    e.g. "Command exited with non-zero status 2".
    """

    try:
        lines = [
            line.strip()
            for line in path.read_text(
                encoding="utf-8",
                errors="replace",
            ).splitlines()
            if line.strip()
        ]

    finally:
        path.unlink(
            missing_ok=True
        )

    elapsed = None
    peak_rss_kib = None

    for line in lines:
        if elapsed is None:
            try:
                elapsed = float(line)
                continue

            except ValueError:
                pass

        if peak_rss_kib is None:
            try:
                peak_rss_kib = int(line)
                continue

            except ValueError:
                pass

    if elapsed is None:
        elapsed = python_wall

    return (
        elapsed,
        peak_rss_kib,
    )


def run_benchmark(
    config_path: Path,
) -> dict:
    config_path = (
        config_path.resolve()
    )

    config = load_simple_yaml(
        config_path
    )

    validate_config(config)

    input_cfg = config["input"]
    model_cfg = config["model"]

    input_path = (
        ROOT
        / str(
            input_cfg["path"]
        )
    ).resolve()

    if not input_path.is_file():
        raise FileNotFoundError(
            f"Input not found: "
            f"{input_path}"
        )

    if not SEPARATOR.is_file():
        raise FileNotFoundError(
            f"StemLab CLI not found: "
            f"{SEPARATOR}"
        )

    if shutil.which(
        "ffprobe"
    ) is None:
        raise RuntimeError(
            "ffprobe not found"
        )

    time_binary = (
        "/usr/bin/time"
    )

    if not Path(
        time_binary
    ).is_file():
        raise RuntimeError(
            "/usr/bin/time not found"
        )

    actual_input_hash = sha256(
        input_path
    )

    expected_input_hash = str(
        input_cfg["sha256"]
    )

    if (
        actual_input_hash
        != expected_input_hash
    ):
        raise RuntimeError(
            "Input SHA-256 mismatch.\n"
            f"Expected: "
            f"{expected_input_hash}\n"
            f"Actual:   "
            f"{actual_input_hash}\n"
            "Refusing to run a "
            "non-reproducible experiment."
        )

    info = audio_info(
        input_path
    )

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    experiment = str(
        config["experiment"]
    )

    preset = str(
        model_cfg["preset"]
    )

    requested_model_name = str(
        model_cfg["name"]
    )

    timestamp = datetime.now(
        timezone.utc
    ).strftime(
        "%Y%m%dT%H%M%SZ"
    )

    run_id = (
        f"{timestamp}-"
        f"{experiment}-"
        f"{preset}-"
        f"{actual_input_hash[:8]}"
    )

    result_dir = (
        RESULTS_DIR
        / run_id
    )

    output_dir = (
        result_dir
        / "stems"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    with tempfile.NamedTemporaryFile(
        mode="w+",
        prefix="stemlab-time-",
        suffix=".txt",
        delete=False,
    ) as tf:
        time_file = Path(
            tf.name
        )

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

    print(
        f"Preset: {preset}"
    )
    print(
        f"Requested model: "
        f"{requested_model_name}"
    )
    print(
        f"Input:  {input_path}"
    )
    print(
        f"Output: {output_dir}"
    )

    started_utc = datetime.now(
        timezone.utc
    ).isoformat()

    start = time.perf_counter()

    process = subprocess.run(
        command,
        capture_output=True,
        text=True,
    )

    python_wall = (
        time.perf_counter()
        - start
    )

    finished_utc = datetime.now(
        timezone.utc
    ).isoformat()

    stdout = (
        process.stdout
        or ""
    )

    stderr = (
        process.stderr
        or ""
    )

    if stdout:
        print(
            stdout,
            end=""
            if stdout.endswith("\n")
            else "\n",
        )

    if stderr:
        print(
            stderr,
            end=""
            if stderr.endswith("\n")
            else "\n",
            file=sys.stderr,
        )

    combined_output = (
        stdout
        + "\n"
        + stderr
    )

    resolved_model_name = (
        parse_resolved_model(
            combined_output
        )
    )

    if resolved_model_name is None:
        resolved_model_name = (
            requested_model_name
        )

    end_to_end, peak_ram_kib = (
        parse_time_file(
            time_file,
            python_wall,
        )
    )

    outputs = []

    for path in sorted(
        output_dir.rglob("*")
    ):
        if not path.is_file():
            continue

        try:
            metadata = audio_info(
                path
            )

        except Exception:
            metadata = {}

        outputs.append(
            {
                "path":
                    str(
                        path.relative_to(
                            ROOT
                        )
                    ),
                "bytes":
                    path.stat().st_size,
                "sha256":
                    sha256(path),
                **metadata,
            }
        )

    duration = info[
        "duration_seconds"
    ]

    resolved_provenance = (
        model_provenance(
            resolved_model_name
        )
    )

    requested_provenance = (
        model_provenance(
            requested_model_name
        )
    )

    result = {
        "schema_version": 3,

        "run_id":
            run_id,

        "experiment":
            experiment,

        "config": {
            "path":
                str(
                    config_path.relative_to(
                        ROOT
                    )
                ),
            "sha256":
                sha256(
                    config_path
                ),
        },

        "started_utc":
            started_utc,

        "finished_utc":
            finished_utc,

        "input": {
            "path":
                str(
                    input_path.relative_to(
                        ROOT
                    )
                ),

            "sha256":
                actual_input_hash,

            "material":
                input_cfg.get(
                    "material"
                ),

            "excerpt_start_seconds":
                input_cfg.get(
                    "excerpt_start_seconds"
                ),

            "excerpt_duration_seconds":
                input_cfg.get(
                    "excerpt_duration_seconds"
                ),

            **info,
        },

        "model": {
            "engine":
                model_cfg["engine"],

            "preset":
                preset,

            "requested_name":
                requested_model_name,

            "name":
                resolved_model_name,

            "resolved_name":
                resolved_model_name,

            "requested_provenance":
                requested_provenance,

            "provenance":
                resolved_provenance,
        },

        "software":
            software_info(),

        "environment":
            environment_info(),

        "measurement": {
            "end_to_end_seconds":
                end_to_end,

            "python_wall_seconds":
                python_wall,

            "rtf_end_to_end":
                (
                    end_to_end
                    / duration
                    if duration > 0
                    else None
                ),

            "peak_rss_kib":
                peak_ram_kib,

            "peak_rss_bytes":
                (
                    peak_ram_kib
                    * 1024
                    if peak_ram_kib
                    is not None
                    else None
                ),
        },

        "process": {
            "command":
                command,

            "exit_code":
                process.returncode,

            "success":
                (
                    process.returncode
                    == 0
                ),
        },

        "outputs":
            outputs,
    }

    result_file = (
        result_dir
        / "result.json"
    )

    result_file.write_text(
        json.dumps(
            result,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return result


def main():
    parser = argparse.ArgumentParser(
        description=(
            "StemLab reproducible "
            "benchmark runner"
        )
    )

    parser.add_argument(
        "config",
        type=Path,
        help=(
            "Benchmark experiment "
            "YAML configuration"
        ),
    )

    args = parser.parse_args()

    try:
        result = run_benchmark(
            args.config
        )

    except Exception as exc:
        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )
        return 1

    measurement = result[
        "measurement"
    ]

    model = result["model"]

    print()
    print(
        "StemLab benchmark complete"
    )
    print(
        f"Experiment: "
        f"{result['experiment']}"
    )
    print(
        f"Run:        "
        f"{result['run_id']}"
    )
    print(
        f"Requested:  "
        f"{model['requested_name']}"
    )
    print(
        f"Resolved:   "
        f"{model['resolved_name']}"
    )
    print(
        f"Runtime:    "
        f"{measurement['end_to_end_seconds']:.2f} s"
    )
    print(
        f"RTF:        "
        f"{measurement['rtf_end_to_end']:.3f}"
    )

    peak = measurement[
        "peak_rss_bytes"
    ]

    if peak is not None:
        print(
            f"Peak RSS:   "
            f"{peak / (1024 ** 3):.2f} GiB"
        )

    print(
        f"Outputs:    "
        f"{len(result['outputs'])}"
    )
    print(
        f"Result:     "
        f"data/results/"
        f"{result['run_id']}/"
        f"result.json"
    )

    return (
        0
        if result[
            "process"
        ]["success"]
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(
        main()
    )