#!/usr/bin/env python3
"""Isolated StemLab wrapper contract tests; never invoke actual inference."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts" / "stem-separate"


class OfflineWrapperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.venv = base / "isolated venv"
        self.models = base / "models"
        self.output = base / "output"
        self.input = base / "input.wav"
        self.input.write_bytes(b"fixture; never real audio")
        binary = self.venv / "bin" / "audio-separator"
        binary.parent.mkdir(parents=True)
        binary.write_text(
            '#!/bin/sh\n'
            'printf "%s\\n" "$@" > "$STEMLAB_STUB_LOG"\n'
        )
        binary.chmod(0o755)
        self.log = base / "arguments.txt"
        self.env = dict(os.environ, STEM_LAB_VENV=str(self.venv),
                        STEM_LAB_MODELS=str(self.models),
                        STEMLAB_STUB_LOG=str(self.log))

    def run_wrapper(self, *args):
        return subprocess.run(
            ["bash", str(WRAPPER), *args], env=self.env,
            capture_output=True, text=True, timeout=10, check=False,
        )

    def test_cached_model_arguments_do_not_trigger_installer(self):
        result = self.run_wrapper("balanced", str(self.input), str(self.output))
        self.assertEqual(result.returncode, 0, result.stderr)
        args = self.log.read_text().splitlines()
        self.assertEqual(args[0], str(self.input))
        self.assertEqual(args[args.index("--model_filename") + 1], "htdemucs.yaml")
        self.assertEqual(args[args.index("--model_file_dir") + 1], str(self.models))
        self.assertEqual(args[args.index("--output_dir") + 1], str(self.output))
        self.assertTrue(self.models.is_dir())
        self.assertTrue(self.output.is_dir())

    def test_missing_backend_does_not_modify_output_or_models(self):
        (self.venv / "bin/audio-separator").unlink()
        result = self.run_wrapper("balanced", str(self.input), str(self.output))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("audio-separator not found", result.stderr)
        self.assertFalse(self.output.exists())
        self.assertFalse(self.models.exists())

    def test_unknown_preset_rejected_before_directory_creation(self):
        result = self.run_wrapper("unknown", str(self.input), str(self.output))
        self.assertEqual(result.returncode, 2)
        self.assertIn("Unknown preset", result.stderr)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
