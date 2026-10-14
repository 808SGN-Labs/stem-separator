#!/usr/bin/env python3
"""Offline installer contract tests: no real uv, network, or user data touched."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install.sh"


class InstallPreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.bin = base / "bin"
        self.bin.mkdir()
        self.xdg = base / "xdg data"
        self.log = base / "uv-args.txt"
        self.env = dict(os.environ, XDG_DATA_HOME=str(self.xdg),
                        PATH=f"{self.bin}:{os.environ.get('PATH', '')}",
                        STEMLAB_TEST_UV_LOG=str(self.log))
        self.stub("ffmpeg", "#!/bin/sh\nexit 0\n")
        self.stub("uv", '#!/bin/sh\nprintf "%s\\n" "$*" >> "$STEMLAB_TEST_UV_LOG"\n')

    def stub(self, name, content):
        path = self.bin / name
        path.write_text(content)
        path.chmod(0o755)

    def test_installer_targets_isolated_venv_and_pins_backend(self):
        result = subprocess.run(["bash", str(INSTALLER)], env=self.env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = self.log.read_text().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], f"venv --python 3.12 {self.xdg}/808sgn-stem-lab/.venv")
        self.assertIn("audio-separator[cpu]==0.47.0", lines[1])
        self.assertIn("audioread", lines[1])
        self.assertIn(str(self.xdg / "808sgn-stem-lab/.venv/bin/python"), lines[1])

    def test_missing_ffmpeg_is_reported_without_install(self):
        # Restrict PATH to stubs while still exposing bash itself via absolute path.
        self.bin.joinpath("ffmpeg").unlink()
        self.env["PATH"] = str(self.bin)
        result = subprocess.run(["/bin/bash", str(INSTALLER)], env=self.env,
                                capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FFmpeg is required", result.stderr)
        self.assertFalse(self.log.exists())


if __name__ == "__main__":
    unittest.main()
